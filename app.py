from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'itsams-super-secret-key-2024-change-in-production')

@app.template_filter('status_color')
def status_color_filter(index):
    colors = ['#f59e0b', '#4cc9f0', '#10b981', '#6b7280', '#ef4444']
    return colors[(index - 1) % len(colors)]

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',
    'db': 'it_support_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_globals():
    if 'user_id' in session:
        try:
            db = get_db()
            cursor = db.cursor()
            if session.get('role') == 'employee':
                cursor.execute(
                    "SELECT COUNT(*) as count FROM activities WHERE requester_user_id = %s AND status = 'pending'",
                    (session['user_id'],)
                )
            else:
                cursor.execute("SELECT COUNT(*) as count FROM activities WHERE status = 'pending'")
            pending_count = cursor.fetchone()['count']
            db.close()
            return dict(pending_count=pending_count, current_user=session)
        except Exception:
            pass
    return dict(pending_count=0, current_user={})

# ===================== AUTH =====================

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'employee':
            return redirect(url_for('my_tickets'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s AND is_active = 1", (username,))
            user = cursor.fetchone()
            db.close()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user['role']
                session['email'] = user['email']
                flash(f'Welcome back, {user["full_name"]}!', 'success')
                if user['role'] == 'employee':
                    return redirect(url_for('my_tickets'))
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            flash(f'Database error: {e}. Please ensure XAMPP MySQL is running.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ===================== DASHBOARD =====================

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'employee':
        return redirect(url_for('my_tickets'))
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM activities WHERE status = 'pending'")
    pending = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM activities WHERE status = 'in_progress'")
    in_progress = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM activities WHERE status = 'resolved'")
    resolved = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM activities WHERE DATE(created_at) = CURDATE()")
    today_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1 AND role = 'it_staff'")
    staff_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM activities")
    total_tickets = cursor.fetchone()['count']

    cursor.execute("""
         SELECT a.*, c.name as category_name, c.icon as category_icon,
             u.full_name as staff_name
        FROM activities a
        LEFT JOIN categories c ON a.category_id = c.id
        LEFT JOIN users u ON a.assigned_to = u.id
        ORDER BY a.created_at DESC LIMIT 8
    """)
    recent_activities = cursor.fetchall()

    cursor.execute("""
        SELECT c.name, COUNT(a.id) as count
        FROM categories c
        LEFT JOIN activities a ON a.category_id = c.id
        GROUP BY c.id, c.name ORDER BY count DESC
    """)
    category_stats = cursor.fetchall()

    cursor.execute("""
        SELECT status, COUNT(*) as count FROM activities GROUP BY status
    """)
    status_stats = cursor.fetchall()

    cursor.execute("""
        SELECT DATE_FORMAT(created_at, '%b %Y') as month, COUNT(*) as count
        FROM activities WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%Y-%m') ORDER BY MIN(created_at) ASC
    """)
    monthly_stats = cursor.fetchall()

    cursor.execute("""
        SELECT priority, COUNT(*) as count FROM activities GROUP BY priority
    """)
    priority_stats = cursor.fetchall()

    cursor.execute("""
        SELECT u.full_name, COUNT(a.id) as total,
               SUM(CASE WHEN a.status = 'resolved' THEN 1 ELSE 0 END) as resolved
        FROM users u LEFT JOIN activities a ON a.assigned_to = u.id
        WHERE u.role = 'it_staff' AND u.is_active = 1
        GROUP BY u.id, u.full_name ORDER BY total DESC LIMIT 5
    """)
    top_staff = cursor.fetchall()

    db.close()
    return render_template('dashboard.html',
        pending=pending, in_progress=in_progress, resolved=resolved,
        today_count=today_count,
        staff_count=staff_count, total_tickets=total_tickets,
        recent_activities=recent_activities, category_stats=category_stats,
        status_stats=status_stats, monthly_stats=monthly_stats,
        priority_stats=priority_stats, top_staff=top_staff)

# ===================== ACTIVITIES =====================

@app.route('/activities')
@login_required
def activities():
    db = get_db()
    cursor = db.cursor()
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '')

    query = """
         SELECT a.*, c.name as category_name, c.icon as category_icon,
             u.full_name as staff_name
        FROM activities a
        LEFT JOIN categories c ON a.category_id = c.id
        LEFT JOIN users u ON a.assigned_to = u.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        query += " AND a.status = %s"
        params.append(status_filter)
    if priority_filter:
        query += " AND a.priority = %s"
        params.append(priority_filter)
    if category_filter:
        query += " AND a.category_id = %s"
        params.append(category_filter)
    if search:
        query += " AND (a.title LIKE %s OR a.ticket_no LIKE %s OR a.requester_name LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    query += " ORDER BY a.created_at DESC"
    cursor.execute(query, params)
    activity_list = cursor.fetchall()

    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()
    db.close()
    return render_template('activities/list.html',
        activities=activity_list, categories=categories,
        status_filter=status_filter, priority_filter=priority_filter,
        category_filter=category_filter, search=search)

@app.route('/activities/add', methods=['GET', 'POST'])
@login_required
def add_activity():
    flash('Manual ticket creation is disabled. Only employees can submit new requests.', 'warning')
    if session.get('role') == 'employee':
        return redirect(url_for('submit_ticket'))
    return redirect(url_for('activities'))

@app.route('/activities/<int:activity_id>')
@login_required
def view_activity(activity_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT a.*, c.name as category_name, c.icon as category_icon,
               u.full_name as staff_name, u.email as staff_email, u.phone as staff_phone,
               cu.full_name as created_by_name
        FROM activities a
        LEFT JOIN categories c ON a.category_id = c.id
        LEFT JOIN users u ON a.assigned_to = u.id
        LEFT JOIN users cu ON a.created_by = cu.id
        WHERE a.id = %s
    """, (activity_id,))
    activity = cursor.fetchone()
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('activities'))

    cursor.execute("""
        SELECT al.*, u.full_name as user_name
        FROM activity_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.activity_id = %s ORDER BY al.created_at ASC
    """, (activity_id,))
    logs = cursor.fetchall()
    cursor.execute("""
        SELECT tc.*, u.full_name as commenter_name, u.role as commenter_role
        FROM ticket_comments tc
        LEFT JOIN users u ON tc.user_id = u.id
        WHERE tc.activity_id = %s
        ORDER BY tc.created_at ASC
    """, (activity_id,))
    comments = cursor.fetchall()
    cursor.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY full_name")
    staff = cursor.fetchall()
    db.close()
    return render_template('activities/view.html', activity=activity, logs=logs, comments=comments, staff=staff)

@app.route('/activities/<int:activity_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_activity(activity_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM activities WHERE id = %s", (activity_id,))
    activity = cursor.fetchone()
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('activities'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        requester_name = request.form.get('requester_name', '').strip()
        requester_department = request.form.get('requester_department', '').strip()
        priority = request.form.get('priority', 'medium')
        old_status = activity['status']
        new_status = request.form.get('status', old_status)
        notes = request.form.get('notes', '').strip()

        if not title or not category_id or not requester_name:
            flash('Title, Category, and Requester are required.', 'danger')
        else:
            started_at = activity['started_at']
            resolved_at = activity['resolved_at']
            if new_status == 'in_progress' and old_status == 'pending':
                started_at = datetime.now()
            if new_status in ['resolved', 'closed'] and old_status not in ['resolved', 'closed']:
                resolved_at = datetime.now()

            cursor.execute("""
                UPDATE activities SET title=%s, description=%s, category_id=%s,
                    requester_name=%s, requester_department=%s,
                    priority=%s, status=%s,
                    started_at=%s, resolved_at=%s, notes=%s, updated_at=NOW()
                WHERE id=%s
            """, (title, description, category_id, requester_name,
                  requester_department or None,
                  priority, new_status, started_at, resolved_at, notes, activity_id))

            action_detail = f'Status changed from {old_status} to {new_status}' if old_status != new_status else 'Activity details updated'
            cursor.execute("""
                INSERT INTO activity_logs (activity_id, user_id, action, details)
                VALUES (%s, %s, %s, %s)
            """, (activity_id, session['user_id'],
                  'status_changed' if old_status != new_status else 'updated', action_detail))
            db.commit()
            db.close()
            flash('Activity updated successfully!', 'success')
            return redirect(url_for('view_activity', activity_id=activity_id))

    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()
    db.close()
    return render_template('activities/edit.html',
        activity=activity, categories=categories)

@app.route('/activities/<int:activity_id>/delete', methods=['POST'])
@admin_required
def delete_activity(activity_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM activity_logs WHERE activity_id = %s", (activity_id,))
    cursor.execute("DELETE FROM activities WHERE id = %s", (activity_id,))
    db.commit()
    db.close()
    flash('Activity deleted successfully.', 'success')
    return redirect(url_for('activities'))

@app.route('/activities/<int:activity_id>/update-status', methods=['POST'])
@login_required
def update_activity_status(activity_id):
    new_status = request.form.get('status')
    valid_statuses = ['pending', 'in_progress', 'resolved', 'closed', 'cancelled']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('view_activity', activity_id=activity_id))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT status FROM activities WHERE id = %s", (activity_id,))
    old = cursor.fetchone()
    if old:
        updates = "status = %s, updated_at = NOW()"
        params = [new_status]
        if new_status == 'in_progress' and old['status'] == 'pending':
            updates += ", started_at = NOW()"
        if new_status in ['resolved', 'closed'] and old['status'] not in ['resolved', 'closed']:
            updates += ", resolved_at = NOW()"
        params.append(activity_id)
        cursor.execute(f"UPDATE activities SET {updates} WHERE id = %s", params)
        cursor.execute("""
            INSERT INTO activity_logs (activity_id, user_id, action, details)
            VALUES (%s, %s, %s, %s)
        """, (activity_id, session['user_id'], 'status_changed',
              f'Status changed from {old["status"]} to {new_status}'))
        db.commit()
        flash('Status updated successfully!', 'success')
    db.close()
    return redirect(url_for('view_activity', activity_id=activity_id))

@app.route('/activities/<int:activity_id>/accept', methods=['POST'])
@login_required
def accept_activity(activity_id):
    if session.get('role') not in ['it_staff', 'admin']:
        flash('Access denied.', 'danger')
        return redirect(url_for('activities'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ticket_no, assigned_to, status FROM activities WHERE id = %s", (activity_id,))
    activity = cursor.fetchone()
    if not activity:
        flash('Ticket not found.', 'danger')
        db.close()
        return redirect(url_for('activities'))

    if activity['assigned_to'] and activity['assigned_to'] != session['user_id'] and session.get('role') != 'admin':
        flash('This ticket is already being handled by another IT staff.', 'warning')
        db.close()
        return redirect(url_for('activities'))

    updates = "assigned_to = %s, updated_at = NOW()"
    params = [session['user_id']]
    if activity['status'] == 'pending':
        updates += ", status = 'in_progress', started_at = NOW()"
    params.append(activity_id)
    cursor.execute(f"UPDATE activities SET {updates} WHERE id = %s", params)

    cursor.execute("""
        INSERT INTO activity_logs (activity_id, user_id, action, details)
        VALUES (%s, %s, %s, %s)
    """, (
        activity_id,
        session['user_id'],
        'accepted',
        f"Ticket {activity['ticket_no']} accepted by {session.get('full_name', 'IT Staff')}"
    ))
    db.commit()
    db.close()
    flash('Ticket accepted. You are now handling this ticket.', 'success')
    return redirect(url_for('activities'))


@app.route('/notifications')
@login_required
def notifications_redirect():
    if session.get('role') == 'employee':
        return redirect(url_for('my_tickets', status='pending'))
    return redirect(url_for('activities', status='pending'))

# ===================== EMPLOYEE PORTAL =====================

@app.route('/my-tickets')
@login_required
def my_tickets():
    if session.get('role') != 'employee':
        return redirect(url_for('activities'))
    db = get_db()
    cursor = db.cursor()
    status_filter = request.args.get('status', '')
    query = """
        SELECT a.*, c.name as category_name, c.icon as category_icon,
               u.full_name as staff_name
        FROM activities a
        LEFT JOIN categories c ON a.category_id = c.id
        LEFT JOIN users u ON a.assigned_to = u.id
        WHERE a.requester_user_id = %s
    """
    params = [session['user_id']]
    if status_filter:
        query += " AND a.status = %s"
        params.append(status_filter)
    query += " ORDER BY a.created_at DESC"
    cursor.execute(query, params)
    ticket_list = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE requester_user_id = %s AND status = 'pending'", (session['user_id'],))
    my_pending = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE requester_user_id = %s AND status = 'in_progress'", (session['user_id'],))
    my_inprogress = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE requester_user_id = %s AND status IN ('resolved','closed')", (session['user_id'],))
    my_resolved = cursor.fetchone()['c']
    db.close()
    return render_template('employee/my_tickets.html',
        tickets=ticket_list, status_filter=status_filter,
        my_pending=my_pending, my_inprogress=my_inprogress, my_resolved=my_resolved)


@app.route('/my-tickets/submit', methods=['GET', 'POST'])
@login_required
def submit_ticket():
    if session.get('role') != 'employee':
        return redirect(url_for('add_activity'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        priority = request.form.get('priority', 'medium')
        if not title or not category_id:
            flash('Title and Category are required.', 'danger')
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT full_name, department FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            requester_name = user['full_name']
            requester_department = user['department'] or ''
            cursor.execute("SELECT COUNT(*) as count FROM activities")
            count = cursor.fetchone()['count']
            ticket_no = f"TKT-{datetime.now().strftime('%Y%m')}-{str(count + 1).zfill(4)}"
            cursor.execute("""
                INSERT INTO activities (ticket_no, title, description, category_id, requester_name,
                    requester_department, requester_user_id, priority, status, created_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, '')
            """, (ticket_no, title, description, category_id, requester_name,
                  requester_department, session['user_id'], priority, session['user_id']))
            activity_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO activity_logs (activity_id, user_id, action, details)
                VALUES (%s, %s, %s, %s)
            """, (activity_id, session['user_id'], 'created',
                  f'Ticket {ticket_no} submitted by {requester_name}'))
            db.commit()
            db.close()
            flash(f'Your request {ticket_no} has been submitted! Our IT team will review it shortly.', 'success')
            return redirect(url_for('my_tickets'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()
    db.close()
    return render_template('employee/submit.html', categories=categories)


@app.route('/my-tickets/<int:ticket_id>')
@login_required
def view_my_ticket(ticket_id):
    if session.get('role') != 'employee':
        return redirect(url_for('view_activity', activity_id=ticket_id))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT a.*, c.name as category_name, c.icon as category_icon,
               u.full_name as staff_name, u.email as staff_email, u.phone as staff_phone
        FROM activities a
        LEFT JOIN categories c ON a.category_id = c.id
        LEFT JOIN users u ON a.assigned_to = u.id
        WHERE a.id = %s AND a.requester_user_id = %s
    """, (ticket_id, session['user_id']))
    ticket = cursor.fetchone()
    if not ticket:
        flash('Ticket not found.', 'danger')
        db.close()
        return redirect(url_for('my_tickets'))
    cursor.execute("""
        SELECT tc.*, u.full_name as commenter_name, u.role as commenter_role
        FROM ticket_comments tc
        LEFT JOIN users u ON tc.user_id = u.id
        WHERE tc.activity_id = %s AND tc.is_internal = 0
        ORDER BY tc.created_at ASC
    """, (ticket_id,))
    comments = cursor.fetchall()
    cursor.execute("""
        SELECT al.*, u.full_name as user_name
        FROM activity_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.activity_id = %s ORDER BY al.created_at ASC
    """, (ticket_id,))
    logs = cursor.fetchall()
    db.close()
    return render_template('employee/view_ticket.html', ticket=ticket, comments=comments, logs=logs)


@app.route('/my-tickets/<int:ticket_id>/rate', methods=['POST'])
@login_required
def rate_ticket(ticket_id):
    if session.get('role') != 'employee':
        flash('Only employees can rate tickets.', 'danger')
        return redirect(url_for('view_activity', activity_id=ticket_id))
    try:
        rating = int(request.form.get('rating', 0))
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        flash('Please select a valid rating (1-5 stars).', 'danger')
        return redirect(url_for('view_my_ticket', ticket_id=ticket_id))
    feedback = request.form.get('feedback', '').strip()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, status, requester_user_id FROM activities WHERE id = %s", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket or ticket['requester_user_id'] != session['user_id']:
        flash('Ticket not found.', 'danger')
        db.close()
        return redirect(url_for('my_tickets'))
    if ticket['status'] not in ['resolved', 'closed']:
        flash('You can only rate resolved or closed tickets.', 'warning')
        db.close()
        return redirect(url_for('view_my_ticket', ticket_id=ticket_id))
    cursor.execute(
        "UPDATE activities SET rating = %s, feedback = %s WHERE id = %s",
        (rating, feedback or None, ticket_id)
    )
    cursor.execute("""
        INSERT INTO activity_logs (activity_id, user_id, action, details)
        VALUES (%s, %s, %s, %s)
    """, (ticket_id, session['user_id'], 'rated', f'Employee gave {rating}/5 star rating'))
    db.commit()
    db.close()
    flash('Thank you for your feedback!', 'success')
    return redirect(url_for('view_my_ticket', ticket_id=ticket_id))


# ===================== COMMENTS =====================

@app.route('/activities/<int:activity_id>/comment', methods=['POST'])
@login_required
def add_comment(activity_id):
    message = request.form.get('message', '').strip()
    is_internal = 1 if request.form.get('is_internal') else 0
    if not message:
        flash('Comment cannot be empty.', 'danger')
        if session.get('role') == 'employee':
            return redirect(url_for('view_my_ticket', ticket_id=activity_id))
        return redirect(url_for('view_activity', activity_id=activity_id))
    if session.get('role') == 'employee':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT requester_user_id FROM activities WHERE id = %s", (activity_id,))
        row = cursor.fetchone()
        if not row or row['requester_user_id'] != session['user_id']:
            flash('Ticket not found.', 'danger')
            db.close()
            return redirect(url_for('my_tickets'))
        is_internal = 0
        cursor.execute("""
            INSERT INTO ticket_comments (activity_id, user_id, message, is_internal)
            VALUES (%s, %s, %s, 0)
        """, (activity_id, session['user_id'], message))
        db.commit()
        db.close()
        return redirect(url_for('view_my_ticket', ticket_id=activity_id))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM activities WHERE id = %s", (activity_id,))
    if not cursor.fetchone():
        flash('Ticket not found.', 'danger')
        db.close()
        return redirect(url_for('activities'))
    cursor.execute("""
        INSERT INTO ticket_comments (activity_id, user_id, message, is_internal)
        VALUES (%s, %s, %s, %s)
    """, (activity_id, session['user_id'], message, is_internal))
    label = 'Internal note' if is_internal else 'Public comment'
    cursor.execute("""
        INSERT INTO activity_logs (activity_id, user_id, action, details)
        VALUES (%s, %s, %s, %s)
    """, (activity_id, session['user_id'], 'commented', f'{label} added by {session["full_name"]}'))
    db.commit()
    db.close()
    flash('Comment added.', 'success')
    return redirect(url_for('view_activity', activity_id=activity_id))


@app.route('/activities/<int:activity_id>/set-resolution', methods=['POST'])
@login_required
def set_resolution(activity_id):
    if session.get('role') == 'employee':
        flash('Access denied.', 'danger')
        return redirect(url_for('my_tickets'))
    resolution = request.form.get('resolution', '').strip()
    if not resolution:
        flash('Resolution notes cannot be empty.', 'danger')
        return redirect(url_for('view_activity', activity_id=activity_id))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM activities WHERE id = %s", (activity_id,))
    if not cursor.fetchone():
        flash('Ticket not found.', 'danger')
        db.close()
        return redirect(url_for('activities'))
    cursor.execute(
        "UPDATE activities SET resolution = %s, updated_at = NOW() WHERE id = %s",
        (resolution, activity_id)
    )
    cursor.execute("""
        INSERT INTO activity_logs (activity_id, user_id, action, details)
        VALUES (%s, %s, %s, %s)
    """, (activity_id, session['user_id'], 'resolution_added',
          f'Resolution notes added by {session["full_name"]}'))
    db.commit()
    db.close()
    flash('Resolution notes saved.', 'success')
    return redirect(url_for('view_activity', activity_id=activity_id))


# ===================== EMPLOYEES =====================

@app.route('/employees')
@login_required
def employees():
    flash('Employee module has been removed. This system is for IT staff and admin only.', 'info')
    return redirect(url_for('activities'))

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    flash('Employee module has been removed.', 'info')
    return redirect(url_for('activities'))

@app.route('/employees/<int:emp_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    flash('Employee module has been removed.', 'info')
    return redirect(url_for('activities'))

@app.route('/employees/<int:emp_id>/delete', methods=['POST'])
@admin_required
def delete_employee(emp_id):
    flash('Employee module has been removed.', 'info')
    return redirect(url_for('activities'))

@app.route('/employees/<int:emp_id>/view')
@login_required
def view_employee(emp_id):
    flash('Employee module has been removed.', 'info')
    return redirect(url_for('activities'))

# ===================== IT STAFF =====================

@app.route('/staff')
@admin_required
def staff():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT u.*,
               COUNT(a.id) as total_assigned,
               SUM(CASE WHEN a.status = 'resolved' THEN 1 ELSE 0 END) as total_resolved,
               SUM(CASE WHEN a.status IN ('pending','in_progress') THEN 1 ELSE 0 END) as open_tickets
        FROM users u
        LEFT JOIN activities a ON a.assigned_to = u.id
        GROUP BY u.id ORDER BY u.role, u.full_name
    """)
    staff_list = cursor.fetchall()
    db.close()
    return render_template('staff/list.html', staff=staff_list)

@app.route('/staff/add', methods=['GET', 'POST'])
@admin_required
def add_staff():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'it_staff')
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()

        if not username or not password or not full_name or not email:
            flash('All required fields must be filled.', 'danger')
        elif len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
        elif role not in ('admin', 'it_staff', 'employee'):
            flash('Invalid role selected.', 'danger')
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists.', 'danger')
                db.close()
                return render_template('staff/add.html')
            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, password, full_name, email, role, department, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, hashed_pw, full_name, email, role,
                  department or None, phone or None))
            db.commit()
            db.close()
            flash(f'Staff member {full_name} added successfully!', 'success')
            return redirect(url_for('staff'))
    return render_template('staff/add.html')

@app.route('/staff/<int:staff_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_staff(staff_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (staff_id,))
    staff_member = cursor.fetchone()
    if not staff_member:
        flash('Staff member not found.', 'danger')
        return redirect(url_for('staff'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'it_staff')
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        is_active = 1 if request.form.get('is_active') else 0
        new_password = request.form.get('new_password', '')

        if new_password:
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                db.close()
                return render_template('staff/edit.html', staff=staff_member)
            hashed_pw = generate_password_hash(new_password)
            cursor.execute("""
                UPDATE users SET full_name=%s, email=%s, role=%s, department=%s,
                    phone=%s, is_active=%s, password=%s WHERE id=%s
            """, (full_name, email, role, department or None,
                  phone or None, is_active, hashed_pw, staff_id))
        else:
            cursor.execute("""
                UPDATE users SET full_name=%s, email=%s, role=%s, department=%s,
                    phone=%s, is_active=%s WHERE id=%s
            """, (full_name, email, role, department or None,
                  phone or None, is_active, staff_id))
        db.commit()
        db.close()
        flash('Staff member updated successfully!', 'success')
        return redirect(url_for('staff'))

    db.close()
    return render_template('staff/edit.html', staff=staff_member)

@app.route('/staff/<int:staff_id>/toggle', methods=['POST'])
@admin_required
def toggle_staff(staff_id):
    if staff_id == session.get('user_id'):
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('staff'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT is_active FROM users WHERE id = %s", (staff_id,))
    user = cursor.fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, staff_id))
        db.commit()
        flash('Staff account status updated.', 'success')
    db.close()
    return redirect(url_for('staff'))

# ===================== CATEGORIES =====================

@app.route('/categories')
@admin_required
def categories():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT c.*, COUNT(a.id) as usage_count
        FROM categories c
        LEFT JOIN activities a ON a.category_id = c.id
        GROUP BY c.id ORDER BY c.name
    """)
    cats = cursor.fetchall()
    db.close()
    return render_template('categories/list.html', categories=cats)


@app.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', 'fa-tools').strip()
        if not name:
            flash('Category name is required.', 'danger')
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = %s", (name,))
            if cursor.fetchone():
                flash('A category with that name already exists.', 'danger')
                db.close()
                return render_template('categories/form.html', action='add', cat=None)
            cursor.execute(
                "INSERT INTO categories (name, description, icon) VALUES (%s, %s, %s)",
                (name, description or None, icon)
            )
            db.commit()
            db.close()
            flash(f'Category "{name}" added successfully!', 'success')
            return redirect(url_for('categories'))
    return render_template('categories/form.html', action='add', cat=None)


@app.route('/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_category(cat_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categories WHERE id = %s", (cat_id,))
    cat = cursor.fetchone()
    if not cat:
        flash('Category not found.', 'danger')
        db.close()
        return redirect(url_for('categories'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', 'fa-tools').strip()
        if not name:
            flash('Category name is required.', 'danger')
        else:
            cursor.execute(
                "UPDATE categories SET name=%s, description=%s, icon=%s WHERE id=%s",
                (name, description or None, icon, cat_id)
            )
            db.commit()
            db.close()
            flash(f'Category "{name}" updated.', 'success')
            return redirect(url_for('categories'))
    db.close()
    return render_template('categories/form.html', action='edit', cat=cat)


@app.route('/categories/<int:cat_id>/delete', methods=['POST'])
@admin_required
def delete_category(cat_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE category_id = %s", (cat_id,))
    if cursor.fetchone()['c'] > 0:
        flash('Cannot delete: this category has existing tickets. Reassign them first.', 'danger')
        db.close()
        return redirect(url_for('categories'))
    cursor.execute("DELETE FROM categories WHERE id = %s", (cat_id,))
    db.commit()
    db.close()
    flash('Category deleted.', 'success')
    return redirect(url_for('categories'))


# ===================== REPORTS =====================

@app.route('/reports')
@login_required
def reports():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT c.name, c.icon, COUNT(a.id) as total,
               SUM(CASE WHEN a.status = 'resolved' THEN 1 ELSE 0 END) as resolved,
               SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN a.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress
        FROM categories c LEFT JOIN activities a ON a.category_id = c.id
        GROUP BY c.id, c.name, c.icon ORDER BY total DESC
    """)
    category_report = cursor.fetchall()

    cursor.execute("""
        SELECT u.full_name, u.department,
               COUNT(a.id) as total_assigned,
               SUM(CASE WHEN a.status = 'resolved' THEN 1 ELSE 0 END) as resolved,
               SUM(CASE WHEN a.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM users u LEFT JOIN activities a ON a.assigned_to = u.id
        WHERE u.role = 'it_staff' AND u.is_active = 1
        GROUP BY u.id, u.full_name, u.department ORDER BY total_assigned DESC
    """)
    staff_report = cursor.fetchall()

    cursor.execute("""
        SELECT priority, COUNT(*) as count,
               SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved
        FROM activities GROUP BY priority
        ORDER BY FIELD(priority, 'critical', 'high', 'medium', 'low')
    """)
    priority_report = cursor.fetchall()

    cursor.execute("""
        SELECT DATE_FORMAT(created_at, '%b %Y') as month,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved
        FROM activities WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%Y-%m') ORDER BY MIN(created_at) ASC
    """)
    monthly_trend = cursor.fetchall()

    cursor.execute("""
        SELECT requester_department as department, COUNT(id) as total
        FROM activities
        WHERE requester_department IS NOT NULL AND requester_department != ''
        GROUP BY requester_department ORDER BY total DESC
    """)
    dept_report = cursor.fetchall()

    db.close()
    return render_template('reports/index.html',
        category_report=category_report, staff_report=staff_report,
        priority_report=priority_report, monthly_trend=monthly_trend,
        dept_report=dept_report)

# ===================== PROFILE =====================

@app.route('/profile')
@login_required
def profile():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.execute("""
        SELECT al.*, a.ticket_no, a.title
        FROM activity_logs al LEFT JOIN activities a ON al.activity_id = a.id
        WHERE al.user_id = %s ORDER BY al.created_at DESC LIMIT 15
    """, (session['user_id'],))
    activity_log = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE assigned_to = %s", (session['user_id'],))
    total_assigned = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE assigned_to = %s AND status = 'resolved'", (session['user_id'],))
    total_resolved = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM activities WHERE assigned_to = %s AND status IN ('pending','in_progress')", (session['user_id'],))
    open_tickets = cursor.fetchone()['c']
    db.close()
    return render_template('profile.html', user=user, activity_log=activity_log,
        total_assigned=total_assigned, total_resolved=total_resolved, open_tickets=open_tickets)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')

    if not full_name or not email:
        flash('Name and email are required.', 'danger')
        return redirect(url_for('profile'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if new_password:
        if not current_password or not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'danger')
            db.close()
            return redirect(url_for('profile'))
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'danger')
            db.close()
            return redirect(url_for('profile'))
        hashed_pw = generate_password_hash(new_password)
        cursor.execute("""
            UPDATE users SET full_name=%s, email=%s, phone=%s, password=%s WHERE id=%s
        """, (full_name, email, phone or None, hashed_pw, session['user_id']))
    else:
        cursor.execute("""
            UPDATE users SET full_name=%s, email=%s, phone=%s WHERE id=%s
        """, (full_name, email, phone or None, session['user_id']))

    db.commit()
    db.close()
    session['full_name'] = full_name
    session['email'] = email
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
