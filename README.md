# IT Support Activity Monitoring System

A full-featured web application built with **Python Flask** and **MySQL (XAMPP)** for monitoring IT support activities across an organization.

## Features

- **Dashboard** — Real-time statistics, charts (monthly trend, status distribution, categories, priority), top performers
- **Ticket Management** — Create, view, edit, delete, and update status of IT support tickets
- **Employee Management** — Register and manage company employees who request IT support
- **IT Staff Management** — Manage IT staff accounts with role-based access (Admin vs IT Staff)
- **Reports & Analytics** — Category breakdown, staff performance, priority analysis, department trends
- **Activity Timeline** — Full audit trail of ticket changes
- **User Profile** — Edit personal info and change password
- **Responsive Design** — Works on desktop, tablet, and mobile

## Support Categories

- Printer Issues
- Network / WiFi
- Software Installation
- Hardware Repair
- Email & Accounts
- Data Backup & Recovery
- Security & Antivirus
- VPN & Remote Access
- System Updates
- Others

## Prerequisites

- Python 3.8+
- XAMPP (with MySQL service running)

## Setup Instructions

### 1. Start XAMPP

Open XAMPP Control Panel and **Start** the **MySQL** service (Apache is optional since Flask serves the app).

### 2. Install Python Dependencies

Open a terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

### 3. Initialize the Database

Run the database setup script **once**:

```bash
python init_db.py
```

This will:
- Create the `it_support_db` database
- Create all tables
- Insert sample data (employees, categories, users)

### 4. Run the Application

```bash
python app.py
```

Then open your browser and go to: **http://localhost:5000**

## Default Login Credentials

| Role       | Username   | Password    |
|------------|------------|-------------|
| Admin      | admin      | Admin@1234  |
| IT Staff   | jdelacruz  | Admin@1234  |
| IT Staff   | mreyes     | Admin@1234  |
| IT Staff   | bsantos    | Admin@1234  |

> **Change your passwords after first login!**

## Project Structure

```
ojt act - Activity Monitoring System/
├── app.py                  # Main Flask application
├── init_db.py              # Database initialization script
├── requirements.txt        # Python dependencies
├── README.md
├── static/
│   ├── css/
│   │   └── style.css       # Custom stylesheet
│   └── js/
│       └── main.js         # Custom JavaScript
└── templates/
    ├── base.html           # Base layout with sidebar
    ├── login.html          # Login page
    ├── dashboard.html      # Main dashboard
    ├── profile.html        # User profile
    ├── activities/
    │   ├── list.html       # Ticket list with filters
    │   ├── add.html        # Create new ticket
    │   ├── edit.html       # Edit ticket
    │   └── view.html       # Ticket detail view
    │   ├── list.html       # Employee directory
    │   ├── add.html        # Add employee
    │   ├── edit.html       # Edit employee
    │   └── view.html       # Employee detail + history
    ├── staff/
    │   ├── list.html       # IT staff grid
    │   ├── add.html        # Add staff account
    │   └── edit.html       # Edit staff account
    └── reports/
        └── index.html      # Analytics & reports
```

## Role Permissions

| Feature             | Admin | IT Staff |
|---------------------|-------|----------|
| View Dashboard      | ✅    | ✅       |
| Create Tickets      | ✅    | ✅       |
| Edit Any Ticket     | ✅    | ✅       |
| Delete Tickets      | ✅    | ❌       |
| Manage Employees    | ✅    | ✅       |
| Deactivate Employee | ✅    | ❌       |
| Manage IT Staff     | ✅    | ❌       |
| View Reports        | ✅    | ✅       |
| View All Tickets    | ✅    | Own only |

## Database Configuration

Default XAMPP settings are pre-configured. If your setup differs, edit `app.py`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',       # Your MySQL password
    'db': 'it_support_db',
    ...
}
```
