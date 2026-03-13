"""
IT Support Activity Monitoring System - Database Initialization Script
Run this script ONCE to set up the database, tables, and seed data.
Make sure XAMPP MySQL is running before executing.

Usage: python init_db.py
"""

import pymysql
from werkzeug.security import generate_password_hash

DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = ''
DB_NAME = 'it_support_db'

def get_connection(db=None):
    config = dict(host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
                  charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    if db:
        config['db'] = db
    return pymysql.connect(**config)

def init_database():
    print("=" * 60)
    print(" IT Support Activity Monitoring System - DB Setup")
    print("=" * 60)

    # Create database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    conn.close()
    print(f"[OK] Database '{DB_NAME}' created/verified.")

    conn = get_connection(DB_NAME)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            role ENUM('admin','it_staff') NOT NULL DEFAULT 'it_staff',
            department VARCHAR(100),
            phone VARCHAR(20),
            is_active TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            icon VARCHAR(50) DEFAULT 'fa-tools'
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_no VARCHAR(30) UNIQUE NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            category_id INT,
            requester_name VARCHAR(100),
            requester_department VARCHAR(100),
            assigned_to INT,
            priority ENUM('low','medium','high','critical') DEFAULT 'medium',
            status ENUM('pending','in_progress','resolved','closed','cancelled') DEFAULT 'pending',
            started_at TIMESTAMP NULL,
            resolved_at TIMESTAMP NULL,
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            activity_id INT,
            user_id INT,
            action VARCHAR(100),
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            activity_id INT NOT NULL,
            user_id INT NOT NULL,
            message TEXT NOT NULL,
            is_internal TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)

    # Expand users.role ENUM to include 'employee' if not already done.
    cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
    role_col = cursor.fetchone()
    if role_col and 'employee' not in (role_col.get('Type') or ''):
        cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('admin','it_staff','employee') NOT NULL DEFAULT 'it_staff'")

    # Add new columns to activities if missing.
    for col, definition in [
        ('requester_user_id', 'INT NULL'),
        ('resolution',        'TEXT NULL'),
        ('rating',            'TINYINT NULL'),
        ('feedback',          'TEXT NULL'),
    ]:
        cursor.execute(f"SHOW COLUMNS FROM activities LIKE '{col}'")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE activities ADD COLUMN {col} {definition}")

    conn.commit()

    # Migrate older schema that used employees table.
    cursor.execute("SHOW COLUMNS FROM activities LIKE 'requester_name'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE activities ADD COLUMN requester_name VARCHAR(100) NULL AFTER category_id")

    cursor.execute("SHOW COLUMNS FROM activities LIKE 'requester_department'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE activities ADD COLUMN requester_department VARCHAR(100) NULL AFTER requester_name")

    cursor.execute("SHOW COLUMNS FROM activities LIKE 'employee_id'")
    if cursor.fetchone():
        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'activities'
              AND COLUMN_NAME = 'employee_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (DB_NAME,))
        fk_row = cursor.fetchone()
        if fk_row:
            cursor.execute(f"ALTER TABLE activities DROP FOREIGN KEY `{fk_row['CONSTRAINT_NAME']}`")
        cursor.execute("ALTER TABLE activities DROP COLUMN employee_id")

    cursor.execute("DROP TABLE IF EXISTS employees")
    conn.commit()
    print("[OK] Tables created/verified.")

    # Seed default categories only if the table is empty.
    cursor.execute("SELECT COUNT(*) as c FROM categories")
    if cursor.fetchone()['c'] == 0:
        default_categories = [
            ('Hardware Issue',      'Problems with physical devices: computers, monitors, keyboards, mice, etc.',           'fa-desktop'),
            ('Software / Application', 'Software crashes, installation requests, license issues, application errors.',      'fa-laptop-code'),
            ('Network / Internet',  'No internet connection, slow network, Wi-Fi problems, VPN issues.',                    'fa-network-wired'),
            ('Email / Account',     'Cannot log in, password reset, email not working, account lockout.',                   'fa-envelope'),
            ('Printer / Scanner',   'Printer not working, scanner issues, paper jams, driver problems.',                    'fa-print'),
            ('Data / Backup',       'File recovery, data backup requests, storage issues.',                                 'fa-database'),
            ('Security / Virus',    'Malware, virus alerts, suspicious activity, unauthorized access.',                     'fa-shield-alt'),
            ('Other / General',     'General IT requests that do not fit other categories.',                                 'fa-tools'),
        ]
        for name, description, icon in default_categories:
            cursor.execute(
                "INSERT INTO categories (name, description, icon) VALUES (%s, %s, %s)",
                (name, description, icon)
            )
        conn.commit()
        print("[OK] Default categories seeded.")

    # Ensure required login accounts exist and are updated to requested credentials.
    required_users = [
        ('@admin', 'Admin@123', 'System Administrator', 'admin@company.com', 'admin', 'IT Department', '09001234567'),
        ('jrobles', 'P@ssw0rd1', 'J Robles', 'jrobles@company.com', 'it_staff', 'IT Department', '09170000001'),
        ('aarceta', 'P@ssw0rd2', 'A Arceta', 'aarceta@company.com', 'it_staff', 'IT Department', '09170000002'),
    ]

    for username, plain_password, full_name, email, role, department, phone in required_users:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing = cursor.fetchone()
        existing_by_email = None
        if not existing:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_by_email = cursor.fetchone()
        password_hash = generate_password_hash(plain_password)

        if existing:
            cursor.execute("""
                UPDATE users
                SET password = %s,
                    full_name = %s,
                    email = %s,
                    role = %s,
                    department = %s,
                    phone = %s,
                    is_active = 1
                WHERE username = %s
            """, (password_hash, full_name, email, role, department, phone, username))
        elif existing_by_email:
            cursor.execute("""
                UPDATE users
                SET username = %s,
                    password = %s,
                    full_name = %s,
                    role = %s,
                    department = %s,
                    phone = %s,
                    is_active = 1
                WHERE email = %s
            """, (username, password_hash, full_name, role, department, phone, email))
        else:
            cursor.execute("""
                INSERT INTO users (username, password, full_name, email, role, department, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, password_hash, full_name, email, role, department, phone))

    # Remove legacy seeded usernames so only requested accounts remain.
    cursor.execute(
        "DELETE FROM users WHERE username IN (%s, %s, %s, %s, %s, %s)",
        ('admin', 'jdelacruz', 'mreyes', 'bsantos', 'alex.rosario', 'rey.reyes')
    )
    conn.commit()
    print("[OK] Required user accounts are configured.")

    print("[OK] No sample data seeded (clean setup mode).")

    conn.close()
    print("\n" + "=" * 60)
    print(" Setup Complete!")
    print("=" * 60)
    print("\n Default Login Credentials:")
    print("  Admin Account:")
    print("    Username : @admin")
    print("    Password : Admin@123")
    print("\n Run the app with: python app.py")
    print(" Then open: http://localhost:5000\n")

if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("Make sure XAMPP MySQL service is running!\n")
