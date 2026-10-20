import functools
import os
import secrets
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import (
    get_account_by_id,
    get_db_connection,
    init_db,
    normalize_email,
    normalize_username,
)
from mail_service import send_email, sync_inbox

app = Flask(__name__)
app.secret_key = os.environ.get('LOCALMAIL_SECRET_KEY') or secrets.token_hex(32)
init_db()


def _current_account():
    """Resolve the signed-in session to its database-backed account."""
    return get_account_by_id(session['user_id'])


def login_required(view):
    """
    Decorator to protect routes that require user authentication.
    If the user is not logged in, redirect them to the login page.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash('Please log in first to access this page.', 'warning')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view


@app.route('/')
def index():
    """Root URL redirects to inbox if logged in, or login page if not."""
    if 'user_id' in session:
        return redirect(url_for('inbox'))
    return redirect(url_for('login'))


# -------------------------------------------------------------
# AUTHENTICATION ROUTES
# -------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration:
    - GET: renders the registration form
    - POST: validates input, hashes the password, and creates the user in SQLite
    """
    if request.method == 'POST':
        raw_username = request.form.get('username', '')
        password = request.form.get('password', '')

        if not raw_username.strip() or not password.strip():
            flash('Both username and password are required.', 'danger')
            return render_template('register.html')

        try:
            username = normalize_username(raw_username)
            email = normalize_email(raw_username)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('register.html')

        conn = get_db_connection()
        try:
            with conn:
                existing_user = conn.execute(
                    'SELECT id FROM users WHERE username = ? OR email = ?',
                    (username, email),
                ).fetchone()
                if existing_user:
                    flash('Username is already taken. Please choose another.', 'warning')
                    return render_template('register.html')

                hashed_password = generate_password_hash(password)
                conn.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, hashed_password),
                )
        except sqlite3.IntegrityError:
            flash('Username or email address is already registered.', 'warning')
            return render_template('register.html')
        finally:
            conn.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login:
    - GET: renders login form
    - POST: verifies credentials and establishes user session
    """
    if request.method == 'POST':
        raw_username = request.form.get('username', '')
        password = request.form.get('password', '')

        if not raw_username.strip() or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html')

        try:
            username = normalize_username(raw_username)
            email = normalize_email(raw_username)
        except ValueError:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE username = ? OR email = ?',
                (username, email),
            ).fetchone()
        finally:
            conn.close()

        # Verify username exists and password hash matches
        if user and check_password_hash(user['password_hash'], password):
            # Store user identification in Flask session
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']

            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('inbox'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Clears user session and logs them out."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# -------------------------------------------------------------
# MAILBOX ROUTES (Placeholders for upcoming steps)
# -------------------------------------------------------------

@app.route('/inbox')
@login_required
def inbox():
    """Inbox route: queries and displays incoming emails from SQLite."""
    account = _current_account()
    if account is None:
        session.clear()
        flash('Please log in again to access your mailbox.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        emails = conn.execute(
            '''
            SELECT * FROM emails
            WHERE recipient IN (?, ?) AND folder = 'inbox'
            ORDER BY timestamp DESC
            ''',
            (account['email'], account['username']),
        ).fetchall()
    finally:
        conn.close()
    return render_template('inbox.html', emails=emails)


@app.route('/fetch-mail', methods=['POST'])
@login_required
def fetch_mail_route():
    """Triggers POP3 retrieval stub and persists new incoming messages to SQLite."""
    try:
        count = sync_inbox(session['username'])
        if count > 0:
            flash(f"Retrieved {count} new message{'s' if count != 1 else ''} via POP3!", 'success')
        else:
            flash("POP3 check complete: No new messages found on server.", 'info')
    except (OSError, RuntimeError, ValueError, TimeoutError, ConnectionError) as exc:
        flash(f"Could not retrieve mail via POP3: {exc}", 'danger')
    except Exception as exc:
        app.logger.exception("Unexpected POP3 retrieval error")
        flash(f"Unexpected error while checking mail: {exc}", 'danger')
    return redirect(url_for('inbox'))


@app.route('/mark-read/<int:email_id>', methods=['POST'])
@login_required
def mark_read(email_id):
    """Marks an email as read when opened by the recipient."""
    account = _current_account()
    if account is None:
        return {'status': 'unauthorized'}, 401

    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE emails SET is_read = 1 WHERE id = ? AND recipient IN (?, ?)",
            (email_id, account['email'], account['username']),
        )
        conn.commit()
    finally:
        conn.close()
    return {'status': 'ok'}


@app.route('/sent')
@login_required
def sent():
    """Sent route: displays emails sent by the logged-in user."""
    account = _current_account()
    if account is None:
        session.clear()
        flash('Please log in again to access your mailbox.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        emails = conn.execute(
            '''
            SELECT * FROM emails
            WHERE sender IN (?, ?) AND folder = 'sent'
            ORDER BY timestamp DESC
            ''',
            (account['username'], account['email']),
        ).fetchall()
    finally:
        conn.close()
    return render_template('sent.html', emails=emails)


@app.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    """
    Compose route:
    - GET: renders the email composition form
    - POST: captures recipient, subject, and body, and invokes send_email()
    """
    if request.method == 'POST':
        recipient = request.form.get('recipient', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not recipient:
            flash('Recipient is required.', 'danger')
            return render_template('compose.html')
        if not body:
            flash('Message body cannot be empty.', 'danger')
            return render_template('compose.html')

        # Send through the local SMTP server via mail_service.py
        account = _current_account()
        if account is None:
            session.clear()
            flash('Please log in again to send mail.', 'warning')
            return redirect(url_for('login'))

        success, message = send_email(
            sender=account['email'],
            recipient=recipient,
            subject=subject,
            body=body
        )

        if success:
            flash(f'Email to {recipient} sent successfully!', 'success')
            return redirect(url_for('sent'))
        else:
            flash(f'Failed to send email: {message}', 'danger')
            return render_template('compose.html')

    return render_template('compose.html')


if __name__ == '__main__':
    # Use port 5050 to prevent collision with macOS AirPlay (which uses 5000)
    print("Starting Local Mail System web server at http://127.0.0.1:5050")
    app.run(debug=True, port=5050)
