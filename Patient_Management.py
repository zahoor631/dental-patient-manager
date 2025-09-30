import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import sqlite3
from datetime import datetime, date, timedelta
import calendar
import sys
import traceback
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
import os
import csv
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import re

# Enhanced tkcalendar import with better error handling
TK_CALENDAR_AVAILABLE = False
DateEntry = None

try:
    from tkcalendar import DateEntry
    TK_CALENDAR_AVAILABLE = True
    print("tkcalendar imported successfully")
except ImportError as e:
    print(f"tkcalendar import failed: {e}")
    # Create a simple fallback
    class DateEntry(ttk.Entry):
        def __init__(self, master=None, **kwargs):
            kwargs.pop('date_pattern', None)  # Remove unsupported parameter
            super().__init__(master, **kwargs)
            self.insert(0, date.today().isoformat())

# Setup logging
def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler('dental_app.log', maxBytes=5*1024*1024, backupCount=3),
            logging.StreamHandler(sys.stdout)
        ]
    )

# Database setup with enhanced user management and settings
def setup_database():
    try:
        conn = sqlite3.connect('dental_practice.db')
        cursor = conn.cursor()
        
        # Check if patients table exists and its structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patients'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            # Check if the table has the new columns
            cursor.execute("PRAGMA table_info(patients)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add missing columns if needed
            if 'father_name' not in columns:
                print("Adding father_name column to patients table")
                cursor.execute("ALTER TABLE patients ADD COLUMN father_name TEXT")
            
            if 'date_of_birth' not in columns:
                print("Adding date_of_birth column to patients table")
                cursor.execute("ALTER TABLE patients ADD COLUMN date_of_birth TEXT")
            
            if 'city' not in columns:
                print("Adding city column to patients table")
                cursor.execute("ALTER TABLE patients ADD COLUMN city TEXT")
        else:
            # Create patients table with all columns
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                father_name TEXT,
                date_of_birth TEXT,
                age INTEGER,
                gender TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                area TEXT,
                village TEXT,
                registration_date TEXT
            )
            ''')
        
        # Check and create appointments table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                appointment_date TEXT,
                appointment_time TEXT,
                treatment_type TEXT,
                status TEXT DEFAULT 'Scheduled',
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
            ''')
        else:
            # Check if appointments table has all columns
            cursor.execute("PRAGMA table_info(appointments)")
            appt_columns = [column[1] for column in cursor.fetchall()]
            
            if 'status' not in appt_columns:
                print("Adding status column to appointments table")
                cursor.execute("ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'Scheduled'")
        
        # Medical history table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_history'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                condition TEXT NOT NULL,
                diagnosis_date TEXT,
                severity TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
            ''')
        
        # Enhanced Treatments table with blood pressure tracking and X-ray options
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='treatments'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                treatment_date TEXT,
                treatment_type TEXT,
                treatment_visit TEXT,
                tooth_number TEXT,
                cost REAL DEFAULT 0,
                injection_required TEXT,
                bp_before TEXT,
                bp_after TEXT,
                weight_checked TEXT,
                xray_option TEXT,
                zylocin_spray TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
            ''')
        else:
            # Check if treatments table has all columns
            cursor.execute("PRAGMA table_info(treatments)")
            treatment_columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns if they don't exist
            new_columns = [
                ('cost', 'REAL DEFAULT 0'),
                ('treatment_visit', 'TEXT'),
                ('injection_required', 'TEXT'),
                ('bp_before', 'TEXT'),
                ('bp_after', 'TEXT'),
                ('weight_checked', 'TEXT'),
                ('xray_option', 'TEXT'),
                ('zylocin_spray', 'TEXT')
            ]
            
            for col_name, col_type in new_columns:
                if col_name not in treatment_columns:
                    print(f"Adding {col_name} column to treatments table")
                    cursor.execute(f"ALTER TABLE treatments ADD COLUMN {col_name} {col_type}")
        
        # Enhanced Expenses table for detailed clinic expenditures
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT,
                category TEXT,
                description TEXT,
                amount REAL,
                payment_method TEXT,
                notes TEXT
            )
            ''')
        
        # Treatment pricing table for editable prices
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='treatment_prices'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatment_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                treatment_type TEXT UNIQUE NOT NULL,
                price REAL NOT NULL,
                last_updated TEXT
            )
            ''')
            
            # Insert default treatment prices
            default_prices = [
                ("Checkup", 500),
                ("Cleaning", 1000),
                ("Filling", 2000),
                ("RCT", 5000),
                ("Extraction", 1500),
                ("Crown", 8000),
                ("Bridge", 12000),
                ("Dentures", 15000),
                ("Whitening", 6000),
                ("Zylocin Spray", 300)
            ]
            
            cursor.executemany('''
            INSERT OR REPLACE INTO treatment_prices (treatment_type, price, last_updated)
            VALUES (?, ?, ?)
            ''', [(treatment, price, datetime.now().isoformat()) for treatment, price in default_prices])
        
        # Enhanced settings table with Khuzdar villages
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_name TEXT DEFAULT 'Khurshid Dental Clinic Khuzdar',
                welcome_message TEXT DEFAULT 'Welcome to our Dental Clinic',
                address TEXT DEFAULT 'Khuzdar, Balochistan',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                logo_path TEXT DEFAULT '',
                cities TEXT DEFAULT '["Khuzdar", "Karachi", "Quetta", "Islamabad", "Lahore", "Other"]',
                areas TEXT DEFAULT '["City Center", "Gulshan-e-Khuwaja", "Mughalabad", "Sariab", "Other"]',
                villages TEXT DEFAULT '["Nall", "Zidi", "Mola", "Karkh", "Surab", "Zehri", "Wadh", "Besima", "Sasol", "Baghban", "Other"]',
                treatment_types TEXT DEFAULT '["Checkup", "Cleaning", "Filling", "RCT", "Extraction", "Crown", "Bridge", "Dentures", "Whitening", "Zylocin Spray"]'
            )
            ''')
            
            # Insert default settings
            cursor.execute('''
            INSERT INTO settings (clinic_name, welcome_message, address) 
            VALUES (?, ?, ?)
            ''', ('Khurshid Dental Clinic Khuzdar', 'Welcome to our Dental Clinic', 'Khuzdar, Balochistan'))
        
        # User management table for multiple users with password hashing
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_date TEXT,
                last_login TEXT
            )
            ''')
            
            # Create default admin user with hashed password
            default_password = "admin123"
            password_hash = hashlib.sha256(default_password.encode()).hexdigest()
            cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, role, created_date)
            VALUES (?, ?, ?, ?, ?)
            ''', ('admin', password_hash, 'Administrator', 'admin', datetime.now().isoformat()))
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_treatments_date ON treatments(treatment_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)')
        
        conn.commit()
        conn.close()
        print("Database setup completed successfully")
    except Exception as e:
        print(f"Database setup error: {e}")
        messagebox.showerror("Database Error", f"Failed to setup database: {str(e)}")

# Utility functions for enhanced features
def hash_password(password):
    """Hash a password for storing"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    """Verify a stored password against one provided by user"""
    return stored_hash == hashlib.sha256(provided_password.encode()).hexdigest()

def load_json_setting(setting_value):
    """Load a JSON setting with error handling"""
    if not setting_value:
        return []
    try:
        return json.loads(setting_value)
    except:
        return []

def save_json_setting(data):
    """Save data as JSON string"""
    return json.dumps(data)

# Main application class with enhanced features
class DentalPracticeApp:
    def __init__(self, root):
        try:
            # Setup logging
            setup_logging()
            
            self.root = root
            self.root.title("Khurshid Dental Clinic Khuzdar - Advanced Management System")
            self.root.geometry("1200x750")
            self.root.configure(bg='#f0f8ff')
            
            # Setup database
            setup_database()
            
            # Load settings
            self.load_settings()
            
            # Load treatment prices
            self.load_treatment_prices()
            
            # Current user
            self.current_user = None
            
            # Session management
            self.last_activity = datetime.now()
            
            # RCT visit options
            self.rct_visit_options = ["First Visit", "Second Visit", "Third Visit", "Fourth Visit", "Final Visit"]
            
            # X-ray options
            self.xray_options = ["Not Taken", "Taken Now", "Already Have"]
            
            # Expense categories
            self.expense_categories = [
                "Rent", "Utilities", "Salaries", "Medical Supplies", 
                "Equipment", "Maintenance", "Office Supplies", "Other"
            ]
            
            # Style configuration
            self.setup_styles()
            
            # Setup keyboard shortcuts
            self.setup_keyboard_shortcuts()
            
            # Create login screen
            self.create_login_screen()
            
            print("Application initialized successfully")
            
        except Exception as e:
            self.log_error(f"Error initializing application: {e}", True)
            messagebox.showerror("Initialization Error", f"Failed to initialize application: {str(e)}")

    def log_error(self, error_message, exc_info=True):
        """Log errors with context"""
        user_info = self.current_user['username'] if self.current_user else 'Not logged in'
        logging.error(f"User: {user_info} - {error_message}", exc_info=exc_info)

    def load_treatment_prices(self):
        """Load treatment prices from database"""
        self.treatment_costs = {}
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT treatment_type, price FROM treatment_prices')
            for row in cursor.fetchall():
                self.treatment_costs[row[0]] = row[1]
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading treatment prices: {e}")
            # Set default prices if unable to load
            self.treatment_costs = {
                "Checkup": 500, "Cleaning": 1000, "Filling": 2000, "RCT": 5000,
                "Extraction": 1500, "Crown": 8000, "Bridge": 12000, 
                "Dentures": 15000, "Whitening": 6000, "Zylocin Spray": 300
            }

    def save_treatment_prices(self):
        """Save treatment prices to database"""
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            for treatment, price in self.treatment_costs.items():
                cursor.execute('''
                INSERT OR REPLACE INTO treatment_prices (treatment_type, price, last_updated)
                VALUES (?, ?, ?)
                ''', (treatment, price, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Treatment prices updated successfully")
        except Exception as e:
            self.log_error(f"Error saving treatment prices: {e}")
            messagebox.showerror("Error", f"Failed to save treatment prices: {str(e)}")

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-n>', lambda e: self.show_patient_tab())
        self.root.bind('<Control-a>', lambda e: self.show_appointment_tab())
        self.root.bind('<Control-t>', lambda e: self.show_treatment_tab())
        self.root.bind('<Control-s>', lambda e: self.save_settings())
        self.root.bind('<F5>', lambda e: self.refresh_dashboard())

    def setup_session_timeout(self):
        """Setup automatic session timeout"""
        self.last_activity = datetime.now()
        self.root.bind('<Button-1>', self.reset_session_timer)
        self.root.bind('<Key>', self.reset_session_timer)
        self.check_session_timeout()

    def reset_session_timer(self, event=None):
        """Reset session timer on user activity"""
        self.last_activity = datetime.now()

    def check_session_timeout(self):
        """Check for session timeout"""
        idle_time = (datetime.now() - self.last_activity).total_seconds()
        
        if idle_time > 1800:  # 30 minutes
            if messagebox.askyesno("Session Timeout", "Your session has timed out. Log in again?"):
                self.logout()
            else:
                self.root.quit()
        
        self.root.after(60000, self.check_session_timeout)  # Check every minute

    def logout(self):
        """Logout current user"""
        self.notebook.destroy()
        self.create_login_screen()

    def load_settings(self):
        """Load clinic settings from database"""
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT clinic_name, welcome_message, address, phone, email, logo_path, cities, areas, villages, treatment_types FROM settings WHERE id=1')
            settings = cursor.fetchone()
            
            if settings:
                self.clinic_name = settings[0]
                self.welcome_message = settings[1]
                self.clinic_address = settings[2]
                self.clinic_phone = settings[3] if settings[3] else "Not set"
                self.clinic_email = settings[4] if settings[4] else "Not set"
                self.logo_path = settings[5] if settings[5] else ""
                
                # Load JSON settings
                self.cities = load_json_setting(settings[6])
                self.areas = load_json_setting(settings[7])
                self.villages = load_json_setting(settings[8])
                self.treatment_types = load_json_setting(settings[9])
            else:
                # Default values with Khuzdar villages
                self.clinic_name = "Khurshid Dental Clinic Khuzdar"
                self.welcome_message = "Welcome to our Dental Clinic"
                self.clinic_address = "Khuzdar, Balochistan"
                self.clinic_phone = "Not set"
                self.clinic_email = "Not set"
                self.logo_path = ""
                self.cities = ["Khuzdar", "Karachi", "Quetta", "Islamabad", "Lahore", "Other"]
                self.areas = ["City Center", "Gulshan-e-Khuwaja", "Mughalabad", "Sariab", "Other"]
                self.villages = ["Nall", "Zidi", "Mola", "Karkh", "Surab", "Zehri", "Wadh", "Besima", "Sasol", "Baghban", "Other"]
                self.treatment_types = ["Checkup", "Cleaning", "Filling", "RCT", "Extraction", "Crown", "Bridge", "Dentures", "Whitening", "Zylocin Spray"]
                
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading settings: {e}")
            # Set default values with Khuzdar villages
            self.clinic_name = "Khurshid Dental Clinic Khuzdar"
            self.welcome_message = "Welcome to our Dental Clinic"
            self.clinic_address = "Khuzdar, Balochistan"
            self.clinic_phone = "Not set"
            self.clinic_email = "Not set"
            self.logo_path = ""
            self.cities = ["Khuzdar", "Karachi", "Quetta", "Islamabad", "Lahore", "Other"]
            self.areas = ["City Center", "Gulshan-e-Khuwaja", "Mughalabad", "Sariab", "Other"]
            self.villages = ["Nall", "Zidi", "Mola", "Karkh", "Surab", "Zehri", "Wadh", "Besima", "Sasol", "Baghban", "Other"]
            self.treatment_types = ["Checkup", "Cleaning", "Filling", "RCT", "Extraction", "Crown", "Bridge", "Dentures", "Whitening", "Zylocin Spray"]

    def setup_styles(self):
        """Configure ttk styles"""
        try:
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('TFrame', background='#f0f8ff')
            style.configure('TLabel', background='#f0f8ff', font=('Arial', 10))
            style.configure('TButton', font=('Arial', 10), background='#4CAF50')
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Completed.TLabel', foreground='green')
            style.configure('Cancelled.TLabel', foreground='red')
            style.configure('Login.TFrame', background='#e6f7ff')
            style.configure('Login.TLabel', background='#e6f7ff', font=('Arial', 12))
            style.configure('Login.TButton', font=('Arial', 12), background='#007acc', foreground='white')
            style.configure('Admin.TButton', font=('Arial', 10), background='#ff6b6b', foreground='white')
        except Exception as e:
            self.log_error(f"Style setup error: {e}")

    def create_login_screen(self):
        """Create enhanced login screen with user selection"""
        self.login_frame = ttk.Frame(self.root, style='Login.TFrame')
        self.login_frame.pack(fill='both', expand=True)
        
        # Clinic logo and name
        logo_frame = ttk.Frame(self.login_frame, style='Login.TFrame')
        logo_frame.pack(pady=50)
        
        # Try to load logo if path exists
        self.logo_image = None
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                image = Image.open(self.logo_path)
                image = image.resize((120, 120), Image.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(image)
                logo_label = ttk.Label(logo_frame, image=self.logo_image, background='#e6f7ff')
                logo_label.pack()
            except Exception as e:
                self.log_error(f"Error loading logo: {e}")
        
        clinic_name_label = ttk.Label(logo_frame, text=self.clinic_name, font=('Arial', 20, 'bold'), background='#e6f7ff')
        clinic_name_label.pack(pady=10)
        
        welcome_label = ttk.Label(logo_frame, text=self.welcome_message, font=('Arial', 14), background='#e6f7ff')
        welcome_label.pack(pady=5)
        
        # Login form
        login_form = ttk.Frame(self.login_frame, style='Login.TFrame')
        login_form.pack(pady=30)
        
        # User selection
        ttk.Label(login_form, text="Select User:", style='Login.TLabel').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        self.user_combo = ttk.Combobox(login_form, width=20, font=('Arial', 12), state="readonly")
        self.user_combo.grid(row=0, column=1, padx=10, pady=10)
        self.load_user_combo()
        self.user_combo.bind('<<ComboboxSelected>>', self.on_user_select)
        
        ttk.Label(login_form, text="Password:", style='Login.TLabel').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        self.password_entry = ttk.Entry(login_form, width=20, font=('Arial', 12), show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # Login button
        button_frame = ttk.Frame(self.login_frame, style='Login.TFrame')
        button_frame.pack(pady=20)
        
        login_button = ttk.Button(button_frame, text="Login", command=self.login, style='Login.TButton')
        login_button.pack(pady=10, ipadx=20, ipady=5)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda event: self.login())
        
        # Set focus to password field
        self.password_entry.focus()

    def load_user_combo(self):
        """Load users into the combo box"""
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT username, full_name FROM users ORDER BY username')
            users = cursor.fetchall()
            
            user_list = []
            for user in users:
                user_list.append(f"{user[0]} - {user[1]}")
            
            self.user_combo['values'] = user_list
            if user_list:
                self.user_combo.set(user_list[0])
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading users: {e}")

    def on_user_select(self, event):
        """Handle user selection"""
        self.password_entry.focus()

    def login(self):
        """Handle login process with password verification"""
        user_str = self.user_combo.get()
        password = self.password_entry.get()
        
        if not user_str or not password:
            messagebox.showerror("Login Failed", "Please select a user and enter password")
            return
        
        try:
            username = user_str.split(' - ')[0]
            
            # Verify credentials
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password_hash, full_name, role FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and verify_password(user[2], password):
                # Update last login
                cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user[0]))
                conn.commit()
                
                self.current_user = {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[3],
                    'role': user[4]
                }
                
                self.login_frame.destroy()
                self.create_main_application()
                
                # Setup session timeout after login
                self.setup_session_timeout()
                
                # Check for appointment reminders
                self.check_appointment_reminders()
            else:
                messagebox.showerror("Login Failed", "Invalid password")
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error during login: {e}")
            messagebox.showerror("Login Error", f"Error during login: {str(e)}")

    def create_main_application(self):
        """Create the main application after successful login"""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create frames for each tab
        self.create_tabs()
        
        # Initialize each tab
        self.create_dashboard()
        self.create_patient_tab()
        self.create_appointment_tab()
        self.create_treatment_tab()
        self.create_medical_tab()
        self.create_expenses_tab()
        self.create_reports_tab()
        self.create_settings_tab()
        
        # Add user management tab for admin users
        if self.current_user['role'] == 'admin':
            self.create_user_management_tab()
        
        # Load initial data
        self.load_initial_data()
        
        # Set up auto-refresh for dashboard
        self.auto_refresh_dashboard()

    def create_tabs(self):
        """Create all tab frames"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.patient_frame = ttk.Frame(self.notebook)
        self.appointment_frame = ttk.Frame(self.notebook)
        self.treatment_frame = ttk.Frame(self.notebook)
        self.medical_frame = ttk.Frame(self.notebook)
        self.expenses_frame = ttk.Frame(self.notebook)
        self.reports_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.dashboard_frame, text='Dashboard')
        self.notebook.add(self.patient_frame, text='Patient Management')
        self.notebook.add(self.appointment_frame, text='Appointments')
        self.notebook.add(self.treatment_frame, text='Treatments')
        self.notebook.add(self.medical_frame, text='Medical History')
        self.notebook.add(self.expenses_frame, text='Expenses')
        self.notebook.add(self.reports_frame, text='Reports')
        self.notebook.add(self.settings_frame, text='Settings')

    def create_user_management_tab(self):
        """Create user management tab for admin users"""
        self.user_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.user_frame, text='User Management')
        
        try:
            # User management frame
            user_mgmt_frame = ttk.LabelFrame(self.user_frame, text="User Management")
            user_mgmt_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # User list frame
            list_frame = ttk.Frame(user_mgmt_frame)
            list_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Treeview for users
            columns = ('ID', 'Username', 'Full Name', 'Role', 'Created', 'Last Login')
            self.user_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
            
            col_widths = [50, 100, 150, 80, 120, 120]
            for i, col in enumerate(columns):
                self.user_tree.heading(col, text=col)
                self.user_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.user_tree.yview)
            self.user_tree.configure(yscrollcommand=scrollbar.set)
            self.user_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # User form frame
            form_frame = ttk.LabelFrame(user_mgmt_frame, text="Add/Edit User")
            form_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Username:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.user_username = ttk.Entry(form_frame, width=20)
            self.user_username.grid(row=0, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Full Name:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            self.user_fullname = ttk.Entry(form_frame, width=20)
            self.user_fullname.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Role:*", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.user_role = ttk.Combobox(form_frame, values=['admin', 'user'], width=18, state="readonly")
            self.user_role.set('user')
            self.user_role.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Password:*", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.user_password = ttk.Entry(form_frame, width=20, show="*")
            self.user_password.grid(row=3, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Confirm Password:*", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.user_confirm_password = ttk.Entry(form_frame, width=20, show="*")
            self.user_confirm_password.grid(row=4, column=1, sticky='w', padx=5, pady=5)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=5, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Add User", command=self.add_user).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update User", command=self.update_user).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete User", command=self.delete_user).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_user_form).pack(side='left', padx=5)
            
            # Bind selection event
            self.user_tree.bind('<<TreeviewSelect>>', self.on_user_select_management)
            
            # Load users
            self.load_users()
            
        except Exception as e:
            self.log_error(f"Error creating user management tab: {e}")

    def add_user(self):
        """Add a new user"""
        username = self.user_username.get().strip()
        full_name = self.user_fullname.get().strip()
        role = self.user_role.get().strip()
        password = self.user_password.get()
        confirm_password = self.user_confirm_password.get()
        
        # Validate inputs
        if not username or not full_name or not role or not password:
            messagebox.showerror("Error", "All fields are required")
            return
        
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return
        
        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters long")
            return
        
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                messagebox.showerror("Error", "Username already exists")
                return
            
            # Hash password
            password_hash = hash_password(password)
            
            # Insert user
            cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, role, created_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, full_name, role, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            # Refresh user list
            self.load_users()
            
            # Clear form
            self.clear_user_form()
            
            messagebox.showinfo("Success", "User added successfully")
            
        except Exception as e:
            self.log_error(f"Failed to add user: {e}")
            messagebox.showerror("Database Error", f"Failed to add user: {str(e)}")

    def update_user(self):
        """Update selected user"""
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a user to update")
            return
        
        user_id = self.user_tree.item(selected[0])['values'][0]
        username = self.user_username.get().strip()
        full_name = self.user_fullname.get().strip()
        role = self.user_role.get().strip()
        password = self.user_password.get()
        confirm_password = self.user_confirm_password.get()
        
        # Validate inputs
        if not username or not full_name or not role:
            messagebox.showerror("Error", "Username, Full Name, and Role are required")
            return
        
        # If password is provided, validate it
        update_password = False
        if password:
            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters long")
                return
            
            update_password = True
        
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Check if username already exists (excluding current user)
            cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', (username, user_id))
            if cursor.fetchone():
                messagebox.showerror("Error", "Username already exists")
                return
            
            # Update user
            if update_password:
                password_hash = hash_password(password)
                cursor.execute('''
                UPDATE users SET username=?, full_name=?, role=?, password_hash=?
                WHERE id=?
                ''', (username, full_name, role, password_hash, user_id))
            else:
                cursor.execute('''
                UPDATE users SET username=?, full_name=?, role=?
                WHERE id=?
                ''', (username, full_name, role, user_id))
            
            conn.commit()
            conn.close()
            
            # Refresh user list
            self.load_users()
            
            messagebox.showinfo("Success", "User updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update user: {e}")
            messagebox.showerror("Database Error", f"Failed to update user: {str(e)}")

    def delete_user(self):
        """Delete selected user"""
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a user to delete")
            return
        
        user_id = self.user_tree.item(selected[0])['values'][0]
        username = self.user_tree.item(selected[0])['values'][1]
        
        # Prevent deleting the current user
        if user_id == self.current_user['id']:
            messagebox.showerror("Error", "You cannot delete your own account")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user {username}?"):
            return
        
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete user
            cursor.execute('DELETE FROM users WHERE id=?', (user_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh user list
            self.load_users()
            
            # Clear form
            self.clear_user_form()
            
            messagebox.showinfo("Success", "User deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete user: {e}")
            messagebox.showerror("Database Error", f"Failed to delete user: {str(e)}")

    def clear_user_form(self):
        """Clear user form fields"""
        self.user_username.delete(0, tk.END)
        self.user_fullname.delete(0, tk.END)
        self.user_role.set('user')
        self.user_password.delete(0, tk.END)
        self.user_confirm_password.delete(0, tk.END)

    def on_user_select_management(self, event):
        """Load selected user data into form"""
        selected = self.user_tree.selection()
        if not selected:
            return
        
        # Get selected user data
        values = self.user_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_user_form()
        
        # Fill form with selected user data
        self.user_username.insert(0, values[1] if len(values) > 1 else "")
        self.user_fullname.insert(0, values[2] if len(values) > 2 else "")
        self.user_role.set(values[3] if len(values) > 3 else "user")
        # Don't fill passwords for security

    def load_users(self):
        """Load users from database"""
        try:
            # Clear current items
            for item in self.user_tree.get_children():
                self.user_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch users
            cursor.execute('SELECT id, username, full_name, role, created_date, last_login FROM users ORDER BY username')
            
            # Add users to treeview
            for row in cursor.fetchall():
                self.user_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading users: {e}")

    def create_dashboard(self):
        """Create enhanced dashboard tab"""
        try:
            # Header with clinic info and user info
            header_frame = ttk.Frame(self.dashboard_frame)
            header_frame.pack(fill='x', padx=10, pady=10)
            
            # Clinic logo (smaller size)
            if self.logo_path and os.path.exists(self.logo_path):
                try:
                    image = Image.open(self.logo_path)
                    image = image.resize((60, 60), Image.LANCZOS)
                    self.small_logo_image = ImageTk.PhotoImage(image)
                    logo_label = ttk.Label(header_frame, image=self.small_logo_image)
                    logo_label.grid(row=0, column=0, rowspan=2, padx=10)
                except Exception as e:
                    self.log_error(f"Error loading logo: {e}")
            
            clinic_info_frame = ttk.Frame(header_frame)
            clinic_info_frame.grid(row=0, column=1, sticky='w')
            
            clinic_name_label = ttk.Label(clinic_info_frame, text=self.clinic_name, style='Header.TLabel')
            clinic_name_label.grid(row=0, column=0, sticky='w')
            
            address_label = ttk.Label(clinic_info_frame, text=self.clinic_address)
            address_label.grid(row=1, column=0, sticky='w')
            
            # User info and current date/time
            user_datetime_frame = ttk.Frame(header_frame)
            user_datetime_frame.grid(row=0, column=2, rowspan=2, sticky='e', padx=10)
            
            user_label = ttk.Label(user_datetime_frame, text=f"Logged in as: {self.current_user['full_name']} ({self.current_user['role']})", font=('Arial', 10))
            user_label.pack(anchor='e')
            
            self.date_label = ttk.Label(user_datetime_frame, text="", font=('Arial', 10))
            self.date_label.pack(anchor='e')
            
            self.time_label = ttk.Label(user_datetime_frame, text="", font=('Arial', 10))
            self.time_label.pack(anchor='e')
            
            header_frame.columnconfigure(1, weight=1)
            
            # Update date and time
            self.update_datetime()
            
            # Today's appointments frame
            today_frame = ttk.LabelFrame(self.dashboard_frame, text="Today's Appointments")
            today_frame.pack(fill='x', padx=10, pady=5)
            
            # Treeview for today's appointments
            columns = ('ID', 'Time', 'Patient', 'Treatment', 'Status')
            self.today_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=8)
            
            for col in columns:
                self.today_tree.heading(col, text=col)
                self.today_tree.column(col, width=120)
            
            self.today_tree.pack(fill='x', padx=5, pady=5)
            
            # Statistics frame with more metrics
            stats_frame = ttk.Frame(self.dashboard_frame)
            stats_frame.pack(fill='x', padx=10, pady=10)
            
            # Patient statistics
            patient_stats = ttk.LabelFrame(stats_frame, text="Patient Statistics")
            patient_stats.pack(side='left', fill='both', expand=True, padx=5)
            
            self.total_patients_label = ttk.Label(patient_stats, text="Total Patients: Loading...")
            self.total_patients_label.pack(pady=5)
            
            self.new_patients_label = ttk.Label(patient_stats, text="New This Month: Loading...")
            self.new_patients_label.pack(pady=5)
            
            self.new_patients_week_label = ttk.Label(patient_stats, text="New This Week: Loading...")
            self.new_patients_week_label.pack(pady=5)
            
            # Appointment statistics
            appointment_stats = ttk.LabelFrame(stats_frame, text="Appointment Statistics")
            appointment_stats.pack(side='left', fill='both', expand=True, padx=5)
            
            self.today_appointments_label = ttk.Label(appointment_stats, text="Today's Appointments: Loading...")
            self.today_appointments_label.pack(pady=5)
            
            self.pending_appointments_label = ttk.Label(appointment_stats, text="Pending Appointments: Loading...")
            self.pending_appointments_label.pack(pady=5)
            
            self.completed_appointments_label = ttk.Label(appointment_stats, text="Completed This Month: Loading...")
            self.completed_appointments_label.pack(pady=5)
            
            # Revenue statistics
            revenue_stats = ttk.LabelFrame(stats_frame, text="Revenue Statistics")
            revenue_stats.pack(side='left', fill='both', expand=True, padx=5)
            
            self.monthly_revenue_label = ttk.Label(revenue_stats, text="Monthly Revenue: Loading...")
            self.monthly_revenue_label.pack(pady=5)
            
            self.weekly_revenue_label = ttk.Label(revenue_stats, text="Weekly Revenue: Loading...")
            self.weekly_revenue_label.pack(pady=5)
            
            self.total_revenue_label = ttk.Label(revenue_stats, text="Total Revenue: Loading...")
            self.total_revenue_label.pack(pady=5)
            
            # Expense statistics
            expense_stats = ttk.LabelFrame(stats_frame, text="Expense Statistics")
            expense_stats.pack(side='left', fill='both', expand=True, padx=5)
            
            self.monthly_expenses_label = ttk.Label(expense_stats, text="Monthly Expenses: Loading...")
            self.monthly_expenses_label.pack(pady=5)
            
            self.profit_loss_label = ttk.Label(expense_stats, text="Monthly Profit/Loss: Loading...")
            self.profit_loss_label.pack(pady=5)
            
            # Quick actions frame
            actions_frame = ttk.LabelFrame(self.dashboard_frame, text="Quick Actions")
            actions_frame.pack(fill='x', padx=10, pady=10)
            
            ttk.Button(actions_frame, text="New Patient", command=self.show_patient_tab).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="New Appointment", command=self.show_appointment_tab).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="New Treatment", command=self.show_treatment_tab).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="New Expense", command=self.show_expenses_tab).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="Refresh", command=self.refresh_dashboard).pack(side='left', padx=5)
            
            # Add change password button for current user
            ttk.Button(actions_frame, text="Change Password", command=self.change_password).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="Backup Database", command=self.backup_database).pack(side='left', padx=5)
            
        except Exception as e:
            self.log_error(f"Error creating dashboard: {e}")
            raise

    def update_datetime(self):
        """Update date and time on dashboard"""
        now = datetime.now()
        self.date_label.config(text=now.strftime("%A, %B %d, %Y"))
        self.time_label.config(text=now.strftime("%I:%M:%S %p"))
        self.root.after(1000, self.update_datetime)  # Update every second

    def change_password(self):
        """Change password for current user"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Password")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Current Password:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=10)
        current_password = ttk.Entry(dialog, width=20, show="*")
        current_password.grid(row=0, column=1, sticky='w', padx=5, pady=10)
        
        ttk.Label(dialog, text="New Password:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=10)
        new_password = ttk.Entry(dialog, width=20, show="*")
        new_password.grid(row=1, column=1, sticky='w', padx=5, pady=10)
        
        ttk.Label(dialog, text="Confirm New Password:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=10)
        confirm_password = ttk.Entry(dialog, width=20, show="*")
        confirm_password.grid(row=2, column=1, sticky='w', padx=5, pady=10)
        
        def update_password():
            current = current_password.get()
            new = new_password.get()
            confirm = confirm_password.get()
            
            if not current or not new or not confirm:
                messagebox.showerror("Error", "All fields are required")
                return
            
            if new != confirm:
                messagebox.showerror("Error", "New passwords do not match")
                return
            
            if len(new) < 6:
                messagebox.showerror("Error", "New password must be at least 6 characters long")
                return
            
            try:
                conn = sqlite3.connect('dental_practice.db')
                cursor = conn.cursor()
                
                # Verify current password
                cursor.execute('SELECT password_hash FROM users WHERE id = ?', (self.current_user['id'],))
                result = cursor.fetchone()
                
                if not result or not verify_password(result[0], current):
                    messagebox.showerror("Error", "Current password is incorrect")
                    return
                
                # Update password
                new_hash = hash_password(new)
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, self.current_user['id']))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Password updated successfully")
                dialog.destroy()
                
            except Exception as e:
                self.log_error(f"Failed to update password: {e}")
                messagebox.showerror("Database Error", f"Failed to update password: {str(e)}")
        
        ttk.Button(dialog, text="Update Password", command=update_password).grid(row=3, column=0, columnspan=2, pady=10)
        
        # Set focus to current password field
        current_password.focus()

    def backup_database(self):
        """Create a backup of the database"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"dental_practice_backup_{timestamp}.db"
            
            conn = sqlite3.connect('dental_practice.db')
            backup_conn = sqlite3.connect(backup_file)
            
            conn.backup(backup_conn)
            conn.close()
            backup_conn.close()
            
            messagebox.showinfo("Backup Successful", f"Database backed up to {backup_file}")
        except Exception as e:
            self.log_error(f"Failed to backup database: {e}")
            messagebox.showerror("Backup Error", f"Failed to backup database: {str(e)}")

    def restore_database(self):
        """Restore database from backup"""
        try:
            filename = filedialog.askopenfilename(
                title="Select Backup File",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            if filename:
                # Create a backup of current database first
                self.backup_database()
                
                # Restore from selected backup
                backup_conn = sqlite3.connect(filename)
                conn = sqlite3.connect('dental_practice.db')
                
                backup_conn.backup(conn)
                backup_conn.close()
                conn.close()
                
                messagebox.showinfo("Restore Successful", "Database restored successfully. Please restart the application.")
        except Exception as e:
            self.log_error(f"Failed to restore database: {e}")
            messagebox.showerror("Restore Error", f"Failed to restore database: {str(e)}")

    def export_all_data(self):
        """Export all data to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
            )
            if filename:
                # This would be enhanced to export all tables to CSV and zip them
                messagebox.showinfo("Export", "Export functionality would be implemented here")
        except Exception as e:
            self.log_error(f"Failed to export data: {e}")
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def check_appointment_reminders(self):
        """Check for upcoming appointments"""
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            cursor.execute('''
            SELECT a.appointment_time, p.full_name, a.treatment_type
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.appointment_date = ? AND a.status = 'Scheduled'
            ''', (tomorrow,))
            
            appointments = cursor.fetchall()
            if appointments:
                reminder_msg = "Tomorrow's Appointments:\n\n"
                for appt in appointments:
                    reminder_msg += f"• {appt[0]} - {appt[1]} ({appt[2]})\n"
                
                messagebox.showinfo("Appointment Reminder", reminder_msg)
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error checking reminders: {e}")

    def refresh_dashboard(self):
        """Refresh dashboard data with enhanced statistics"""
        try:
            # Update patient count
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM patients')
            total_patients = cursor.fetchone()[0]
            self.total_patients_label.config(text=f"Total Patients: {total_patients}")
            
            # Update new patients this month
            first_day_month = date.today().replace(day=1)
            cursor.execute('SELECT COUNT(*) FROM patients WHERE registration_date >= ?', 
                          (first_day_month.isoformat(),))
            new_patients_month = cursor.fetchone()[0]
            self.new_patients_label.config(text=f"New This Month: {new_patients_month}")
            
            # Update new patients this week
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            cursor.execute('SELECT COUNT(*) FROM patients WHERE registration_date >= ?', 
                          (start_of_week.isoformat(),))
            new_patients_week = cursor.fetchone()[0]
            self.new_patients_week_label.config(text=f"New This Week: {new_patients_week}")
            
            # Update today's appointments count
            today_str = date.today().isoformat()
            cursor.execute('SELECT COUNT(*) FROM appointments WHERE appointment_date = ?', (today_str,))
            today_appointments = cursor.fetchone()[0]
            self.today_appointments_label.config(text=f"Today's Appointments: {today_appointments}")
            
            # Update pending appointments count
            cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Scheduled'")
            pending_appointments = cursor.fetchone()[0]
            self.pending_appointments_label.config(text=f"Pending Appointments: {pending_appointments}")
            
            # Update completed appointments this month
            cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Completed' AND appointment_date >= ?", 
                          (first_day_month.isoformat(),))
            completed_appointments = cursor.fetchone()[0]
            self.completed_appointments_label.config(text=f"Completed This Month: {completed_appointments}")
            
            # Update revenue statistics
            # Monthly revenue
            cursor.execute('SELECT SUM(cost) FROM treatments WHERE treatment_date >= ?', 
                          (first_day_month.isoformat(),))
            monthly_revenue = cursor.fetchone()[0] or 0
            self.monthly_revenue_label.config(text=f"Monthly Revenue: Rs. {monthly_revenue:,.2f}")
            
            # Weekly revenue
            cursor.execute('SELECT SUM(cost) FROM treatments WHERE treatment_date >= ?', 
                          (start_of_week.isoformat(),))
            weekly_revenue = cursor.fetchone()[0] or 0
            self.weekly_revenue_label.config(text=f"Weekly Revenue: Rs. {weekly_revenue:,.2f}")
            
            # Total revenue
            cursor.execute('SELECT SUM(cost) FROM treatments')
            total_revenue = cursor.fetchone()[0] or 0
            self.total_revenue_label.config(text=f"Total Revenue: Rs. {total_revenue:,.2f}")
            
            # Update expense statistics
            cursor.execute('SELECT SUM(amount) FROM expenses WHERE expense_date >= ?', 
                          (first_day_month.isoformat(),))
            monthly_expenses = cursor.fetchone()[0] or 0
            self.monthly_expenses_label.config(text=f"Monthly Expenses: Rs. {monthly_expenses:,.2f}")
            
            # Calculate profit/loss
            profit_loss = monthly_revenue - monthly_expenses
            profit_text = f"Monthly Profit: Rs. {profit_loss:,.2f}" if profit_loss >= 0 else f"Monthly Loss: Rs. {abs(profit_loss):,.2f}"
            self.profit_loss_label.config(text=profit_text)
            
            # Load today's appointments
            self.load_today_appointments()
            
            conn.close()
            logging.info("Dashboard refreshed successfully")
        except Exception as e:
            self.log_error(f"Error refreshing dashboard: {e}")

    def load_today_appointments(self):
        """Load today's appointments into the dashboard"""
        try:
            # Clear existing data
            for item in self.today_tree.get_children():
                self.today_tree.delete(item)
            
            # Fetch today's appointments from database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            today = date.today().isoformat()
            
            cursor.execute('''
            SELECT a.id, a.appointment_time, p.full_name, a.treatment_type, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.appointment_date = ?
            ORDER BY a.appointment_time
            ''', (today,))
            
            for row in cursor.fetchall():
                self.today_tree.insert('', 'end', values=row)
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading today's appointments: {e}")

    def show_patient_tab(self):
        """Switch to patient tab"""
        self.notebook.select(self.patient_frame)

    def show_appointment_tab(self):
        """Switch to appointment tab"""
        self.notebook.select(self.appointment_frame)
        self.load_appointments()

    def show_treatment_tab(self):
        """Switch to treatment tab"""
        self.notebook.select(self.treatment_frame)
        self.load_treatments()

    def show_expenses_tab(self):
        """Switch to expenses tab"""
        self.notebook.select(self.expenses_frame)
        self.load_expenses()

    def create_patient_tab(self):
        """Create enhanced patient management tab with customizable locations"""
        try:
            # Create a frame with scrollbar for the form
            form_container = ttk.Frame(self.patient_frame)
            form_container.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Create a canvas and scrollbar
            canvas = tk.Canvas(form_container)
            scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Patient form frame
            form_frame = ttk.LabelFrame(scrollable_frame, text="Patient Information")
            form_frame.pack(fill='x', padx=10, pady=5)
            
            # Form fields - Personal Information
            ttk.Label(form_frame, text="Full Name:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.name_entry = ttk.Entry(form_frame, width=30)
            self.name_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Father's Name:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            self.father_name_entry = ttk.Entry(form_frame, width=30)
            self.father_name_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Date of Birth:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            if TK_CALENDAR_AVAILABLE:
                self.dob_entry = DateEntry(form_frame, date_pattern='y-mm-dd', width=27)
            else:
                self.dob_entry = ttk.Entry(form_frame, width=30)
                self.dob_entry.insert(0, "YYYY-MM-DD")
            self.dob_entry.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Age:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.age_entry = ttk.Entry(form_frame, width=30)
            self.age_entry.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Gender:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.gender_combo = ttk.Combobox(form_frame, values=["", "Male", "Female", "Other"], width=27, state="readonly")
            self.gender_combo.set("")
            self.gender_combo.grid(row=4, column=1, sticky='w', padx=5, pady=5)
            
            # Contact Information
            ttk.Label(form_frame, text="Phone:*", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='e', padx=5, pady=5)
            self.phone_entry = ttk.Entry(form_frame, width=30)
            self.phone_entry.grid(row=5, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Address:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky='e', padx=5, pady=5)
            self.address_entry = ttk.Entry(form_frame, width=30)
            self.address_entry.grid(row=6, column=1, sticky='ew', padx=5, pady=5)
            
            # Customizable location fields
            ttk.Label(form_frame, text="City:", font=('Arial', 10, 'bold')).grid(row=7, column=0, sticky='e', padx=5, pady=5)
            self.city_combo = ttk.Combobox(form_frame, values=[""] + self.cities, width=27)
            self.city_combo.set("")
            self.city_combo.grid(row=7, column=1, sticky='w', padx=5, pady=5)
            self.city_combo.bind('<KeyRelease>', self.on_city_keyrelease)
            
            ttk.Label(form_frame, text="Area:", font=('Arial', 10, 'bold')).grid(row=8, column=0, sticky='e', padx=5, pady=5)
            self.area_combo = ttk.Combobox(form_frame, values=[""] + self.areas, width=27)
            self.area_combo.set("")
            self.area_combo.grid(row=8, column=1, sticky='w', padx=5, pady=5)
            self.area_combo.bind('<KeyRelease>', self.on_area_keyrelease)
            
            ttk.Label(form_frame, text="Village:", font=('Arial', 10, 'bold')).grid(row=9, column=0, sticky='e', padx=5, pady=5)
            self.village_combo = ttk.Combobox(form_frame, values=[""] + self.villages, width=27)
            self.village_combo.set("")
            self.village_combo.grid(row=9, column=1, sticky='w', padx=5, pady=5)
            self.village_combo.bind('<KeyRelease>', self.on_village_keyrelease)
            
            form_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=10, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Add Patient", command=self.add_patient).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update Patient", command=self.update_patient).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_patient_form).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Patient", command=self.delete_patient).pack(side='left', padx=5)
            
            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Patient list frame
            list_frame = ttk.LabelFrame(self.patient_frame, text="Patient Records")
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Search frame with advanced search
            search_frame = ttk.Frame(list_frame)
            search_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(search_frame, text="Search:").pack(side='left')
            self.patient_search = ttk.Entry(search_frame)
            self.patient_search.pack(side='left', padx=5, fill='x', expand=True)
            self.patient_search.bind('<KeyRelease>', self.search_patients)
            
            # Advanced search button
            ttk.Button(search_frame, text="Advanced Search", command=self.show_advanced_search).pack(side='left', padx=5)
            ttk.Button(search_frame, text="Import CSV", command=self.import_patients_csv).pack(side='left', padx=5)
            
            # Treeview for patients with additional columns
            columns = ('ID', 'Name', 'Father Name', 'Age', 'Gender', 'Phone', 'City', 'Area', 'Village', 'Reg Date')
            self.patient_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
            
            col_widths = [50, 120, 120, 50, 80, 100, 100, 100, 100, 100]
            for i, col in enumerate(columns):
                self.patient_tree.heading(col, text=col)
                self.patient_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.patient_tree.yview)
            self.patient_tree.configure(yscrollcommand=scrollbar.set)
            self.patient_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind selection event
            self.patient_tree.bind('<<TreeviewSelect>>', self.on_patient_select)
            
        except Exception as e:
            self.log_error(f"Error creating patient tab: {e}")
            raise

    def show_advanced_search(self):
        """Show advanced search dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Patient Search")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Name:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(dialog, text="Phone:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        phone_entry = ttk.Entry(dialog, width=30)
        phone_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(dialog, text="City:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        city_combo = ttk.Combobox(dialog, values=self.cities, width=27)
        city_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(dialog, text="Village:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        village_combo = ttk.Combobox(dialog, values=self.villages, width=27)
        village_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(dialog, text="Gender:").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        gender_combo = ttk.Combobox(dialog, values=["", "Male", "Female", "Other"], width=27, state="readonly")
        gender_combo.grid(row=4, column=1, sticky='w', padx=5, pady=5)
        
        def perform_search():
            name = name_entry.get().strip()
            phone = phone_entry.get().strip()
            city = city_combo.get().strip()
            village = village_combo.get().strip()
            gender = gender_combo.get().strip()
            
            self.advanced_patient_search(name, phone, city, village, gender)
            dialog.destroy()
        
        ttk.Button(dialog, text="Search", command=perform_search).grid(row=5, column=0, columnspan=2, pady=10)

    def advanced_patient_search(self, name, phone, city, village, gender):
        """Perform advanced patient search"""
        # Clear current items
        for item in self.patient_tree.get_children():
            self.patient_tree.delete(item)
            
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            query = "SELECT id, full_name, father_name, age, gender, phone, city, area, village, registration_date FROM patients WHERE 1=1"
            params = []
            
            if name:
                query += " AND full_name LIKE ?"
                params.append(f"%{name}%")
            
            if phone:
                query += " AND phone LIKE ?"
                params.append(f"%{phone}%")
            
            if city:
                query += " AND city = ?"
                params.append(city)
            
            if village:
                query += " AND village = ?"
                params.append(village)
            
            if gender:
                query += " AND gender = ?"
                params.append(gender)
            
            cursor.execute(query, params)
            
            for row in cursor.fetchall():
                self.patient_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error in advanced search: {e}")

    def import_patients_csv(self):
        """Import patients from CSV file"""
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    conn = sqlite3.connect('dental_practice.db')
                    cursor = conn.cursor()
                    
                    imported_count = 0
                    for row in reader:
                        # Validate required fields
                        if not row.get('name') or not row.get('phone'):
                            continue
                            
                        cursor.execute('''
                        INSERT INTO patients (full_name, phone, address, city, village, registration_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (row['name'], row['phone'], row.get('address', ''), 
                              row.get('city', ''), row.get('village', ''), date.today().isoformat()))
                        imported_count += 1
                    
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Import Successful", f"{imported_count} patients imported successfully")
                    self.load_patients()
                    
            except Exception as e:
                self.log_error(f"Failed to import patients: {e}")
                messagebox.showerror("Import Error", f"Failed to import patients: {str(e)}")

    def validate_patient_data(self, name, phone):
        """Enhanced data validation"""
        errors = []
        
        if not name or len(name.strip()) < 2:
            errors.append("Name must be at least 2 characters long")
        
        if not phone or not phone.replace('-', '').replace(' ', '').isdigit():
            errors.append("Phone number must contain only digits")
        
        if len(phone) < 10:
            errors.append("Phone number must be at least 10 digits")
        
        return errors

    def validate_email(self, email):
        """Basic email validation"""
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def on_city_keyrelease(self, event):
        """Handle city combo box key release for custom entries"""
        current = self.city_combo.get()
        if current and current not in self.cities:
            # Allow custom entry
            pass

    def on_area_keyrelease(self, event):
        """Handle area combo box key release for custom entries"""
        current = self.area_combo.get()
        if current and current not in self.areas:
            # Allow custom entry
            pass

    def on_village_keyrelease(self, event):
        """Handle village combo box key release for custom entries"""
        current = self.village_combo.get()
        if current and current not in self.villages:
            # Allow custom entry
            pass

    def add_patient(self):
        """Add a new patient to the database"""
        # Get form values
        name = self.name_entry.get().strip()
        father_name = self.father_name_entry.get().strip()
        dob = self.dob_entry.get().strip()
        age = self.age_entry.get().strip()
        gender = self.gender_combo.get().strip()
        phone = self.phone_entry.get().strip()
        address = self.address_entry.get().strip()
        city = self.city_combo.get().strip()
        area = self.area_combo.get().strip()
        village = self.village_combo.get().strip()
        
        # Validate data
        errors = self.validate_patient_data(name, phone)
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
        
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Insert patient
            cursor.execute('''
            INSERT INTO patients (full_name, father_name, date_of_birth, age, gender, phone, address, city, area, village, registration_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, father_name, dob, age, gender, phone, address, city, area, village, date.today().isoformat()))
            
            conn.commit()
            conn.close()
            
            # Refresh patient list
            self.load_patients()
            
            # Clear form
            self.clear_patient_form()
            
            messagebox.showinfo("Success", "Patient added successfully")
            
        except Exception as e:
            self.log_error(f"Failed to add patient: {e}")
            messagebox.showerror("Database Error", f"Failed to add patient: {str(e)}")

    def update_patient(self):
        """Update selected patient"""
        selected = self.patient_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a patient to update")
            return
            
        # Get form values
        name = self.name_entry.get().strip()
        father_name = self.father_name_entry.get().strip()
        dob = self.dob_entry.get().strip()
        age = self.age_entry.get().strip()
        gender = self.gender_combo.get().strip()
        phone = self.phone_entry.get().strip()
        address = self.address_entry.get().strip()
        city = self.city_combo.get().strip()
        area = self.area_combo.get().strip()
        village = self.village_combo.get().strip()
        
        # Validate data
        errors = self.validate_patient_data(name, phone)
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
            
        try:
            patient_id = self.patient_tree.item(selected[0])['values'][0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update patient
            cursor.execute('''
            UPDATE patients 
            SET full_name=?, father_name=?, date_of_birth=?, age=?, gender=?, phone=?, address=?, city=?, area=?, village=?
            WHERE id=?
            ''', (name, father_name, dob, age, gender, phone, address, city, area, village, patient_id))
            
            conn.commit()
            conn.close()
            
            # Refresh patient list
            self.load_patients()
            
            messagebox.showinfo("Success", "Patient updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update patient: {e}")
            messagebox.showerror("Database Error", f"Failed to update patient: {str(e)}")

    def delete_patient(self):
        """Delete selected patient"""
        selected = self.patient_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a patient to delete")
            return
            
        patient_id = self.patient_tree.item(selected[0])['values'][0]
        patient_name = self.patient_tree.item(selected[0])['values'][1]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete patient {patient_name}?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete patient
            cursor.execute('DELETE FROM patients WHERE id=?', (patient_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh patient list
            self.load_patients()
            
            # Clear form
            self.clear_patient_form()
            
            messagebox.showinfo("Success", "Patient deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete patient: {e}")
            messagebox.showerror("Database Error", f"Failed to delete patient: {str(e)}")

    def clear_patient_form(self):
        """Clear all form fields"""
        self.name_entry.delete(0, tk.END)
        self.father_name_entry.delete(0, tk.END)
        if TK_CALENDAR_AVAILABLE:
            self.dob_entry.set_date("")
        else:
            self.dob_entry.delete(0, tk.END)
            self.dob_entry.insert(0, "YYYY-MM-DD")
        self.age_entry.delete(0, tk.END)
        self.gender_combo.set("")
        self.phone_entry.delete(0, tk.END)
        self.address_entry.delete(0, tk.END)
        self.city_combo.set("")
        self.area_combo.set("")
        self.village_combo.set("")

    def on_patient_select(self, event):
        """Load selected patient data into form"""
        selected = self.patient_tree.selection()
        if not selected:
            return
            
        # Get selected patient data
        values = self.patient_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_patient_form()
        
        # Fill form with selected patient data
        self.name_entry.insert(0, values[1] if len(values) > 1 else "")
        self.father_name_entry.insert(0, values[2] if len(values) > 2 else "")
        # Note: Date of birth is not in the treeview display, so we skip it
        self.age_entry.insert(0, values[3] if len(values) > 3 else "")
        self.gender_combo.set(values[4] if len(values) > 4 else "")
        self.phone_entry.insert(0, values[5] if len(values) > 5 else "")
        # Address is not in the treeview display, so we skip it
        self.city_combo.set(values[6] if len(values) > 6 else "")
        self.area_combo.set(values[7] if len(values) > 7 else "")
        self.village_combo.set(values[8] if len(values) > 8 else "")

    def search_patients(self, event):
        """Search patients by name, father's name, or phone"""
        search_term = self.patient_search.get().lower()
        
        # Clear current items
        for item in self.patient_tree.get_children():
            self.patient_tree.delete(item)
            
        # Load patients from database and filter
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, full_name, father_name, age, gender, phone, city, area, village, registration_date FROM patients')
            
            for row in cursor.fetchall():
                if (search_term in str(row[1]).lower() or  # Name
                    search_term in str(row[2]).lower() or  # Father's name
                    search_term in str(row[5]).lower()):   # Phone
                    self.patient_tree.insert('', 'end', values=row)
                    
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error searching patients: {e}")

    def load_patients(self):
        """Load patients from database"""
        try:
            # Clear current items
            for item in self.patient_tree.get_children():
                self.patient_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch patients
            cursor.execute('SELECT id, full_name, father_name, age, gender, phone, city, area, village, registration_date FROM patients')
            
            # Add patients to treeview
            for row in cursor.fetchall():
                self.patient_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading patients: {e}")

    def create_appointment_tab(self):
        """Create appointments management tab"""
        try:
            # Create a frame with scrollbar for the form
            form_container = ttk.Frame(self.appointment_frame)
            form_container.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Create a canvas and scrollbar
            canvas = tk.Canvas(form_container)
            scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Appointment form frame
            form_frame = ttk.LabelFrame(scrollable_frame, text="Appointment Information")
            form_frame.pack(fill='x', padx=10, pady=5)
            
            # Form fields
            ttk.Label(form_frame, text="Patient:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.app_patient_combo = ttk.Combobox(form_frame, width=27, state="readonly")
            self.app_patient_combo.grid(row=0, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Date:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            if TK_CALENDAR_AVAILABLE:
                self.app_date_entry = DateEntry(form_frame, date_pattern='y-mm-dd', width=27)
            else:
                self.app_date_entry = ttk.Entry(form_frame, width=30)
                self.app_date_entry.insert(0, date.today().isoformat())
            self.app_date_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Time:*", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.app_time_combo = ttk.Combobox(form_frame, values=self.generate_time_slots(), width=27, state="readonly")
            self.app_time_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Treatment Type:*", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.app_treatment_combo = ttk.Combobox(form_frame, values=[""] + self.treatment_types, width=27, state="readonly")
            self.app_treatment_combo.set("")
            self.app_treatment_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Status:*", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.app_status_combo = ttk.Combobox(form_frame, values=["Scheduled", "Completed", "Cancelled"], width=27, state="readonly")
            self.app_status_combo.set("Scheduled")
            self.app_status_combo.grid(row=4, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='ne', padx=5, pady=5)
            self.app_notes_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
            self.app_notes_text.grid(row=5, column=1, sticky='ew', padx=5, pady=5)
            
            form_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=6, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Schedule Appointment", command=self.add_appointment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update Appointment", command=self.update_appointment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_appointment_form).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Appointment", command=self.delete_appointment).pack(side='left', padx=5)
            
            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Appointment list frame
            list_frame = ttk.LabelFrame(self.appointment_frame, text="Appointment Schedule")
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Filter frame
            filter_frame = ttk.Frame(list_frame)
            filter_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(filter_frame, text="Filter by Date:").pack(side='left')
            self.app_date_filter = ttk.Entry(filter_frame, width=12)
            self.app_date_filter.insert(0, date.today().isoformat())
            self.app_date_filter.pack(side='left', padx=5)
            
            ttk.Label(filter_frame, text="Filter by Status:").pack(side='left', padx=(20, 5))
            self.app_status_filter = ttk.Combobox(filter_frame, values=["All", "Scheduled", "Completed", "Cancelled"], width=12, state="readonly")
            self.app_status_filter.set("All")
            self.app_status_filter.pack(side='left', padx=5)
            
            ttk.Button(filter_frame, text="Apply Filters", command=self.filter_appointments).pack(side='left', padx=5)
            ttk.Button(filter_frame, text="Clear Filters", command=self.clear_appointment_filters).pack(side='left', padx=5)
            
            # Treeview for appointments
            columns = ('ID', 'Patient', 'Date', 'Time', 'Treatment', 'Status')
            self.appointment_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
            
            col_widths = [50, 150, 100, 80, 120, 100]
            for i, col in enumerate(columns):
                self.appointment_tree.heading(col, text=col)
                self.appointment_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.appointment_tree.yview)
            self.appointment_tree.configure(yscrollcommand=scrollbar.set)
            self.appointment_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind selection event
            self.appointment_tree.bind('<<TreeviewSelect>>', self.on_appointment_select)
            
        except Exception as e:
            self.log_error(f"Error creating appointment tab: {e}")
            raise

    def generate_time_slots(self):
        """Generate time slots for appointments"""
        time_slots = []
        for hour in range(9, 18):  # From 9 AM to 5 PM
            for minute in ['00', '30']:
                time_slots.append(f"{hour:02d}:{minute}")
        return time_slots

    def add_appointment(self):
        """Add a new appointment"""
        patient = self.app_patient_combo.get().strip()
        app_date = self.app_date_entry.get().strip()
        app_time = self.app_time_combo.get().strip()
        treatment = self.app_treatment_combo.get().strip()
        status = self.app_status_combo.get().strip()
        notes = self.app_notes_text.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not patient or not app_date or not app_time or not treatment or not status:
            messagebox.showerror("Error", "Patient, Date, Time, Treatment Type, and Status are required")
            return
        
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Insert appointment
            cursor.execute('''
            INSERT INTO appointments (patient_id, appointment_date, appointment_time, treatment_type, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (patient_id, app_date, app_time, treatment, status, notes))
            
            conn.commit()
            conn.close()
            
            # Refresh appointment list
            self.load_appointments()
            
            # Clear form
            self.clear_appointment_form()
            
            messagebox.showinfo("Success", "Appointment scheduled successfully")
            
        except Exception as e:
            self.log_error(f"Failed to schedule appointment: {e}")
            messagebox.showerror("Database Error", f"Failed to schedule appointment: {str(e)}")

    def update_appointment(self):
        """Update selected appointment"""
        selected = self.appointment_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an appointment to update")
            return
            
        appointment_id = self.appointment_tree.item(selected[0])['values'][0]
        
        patient = self.app_patient_combo.get().strip()
        app_date = self.app_date_entry.get().strip()
        app_time = self.app_time_combo.get().strip()
        treatment = self.app_treatment_combo.get().strip()
        status = self.app_status_combo.get().strip()
        notes = self.app_notes_text.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not patient or not app_date or not app_time or not treatment or not status:
            messagebox.showerror("Error", "Patient, Date, Time, Treatment Type, and Status are required")
            return
            
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update appointment
            cursor.execute('''
            UPDATE appointments 
            SET patient_id=?, appointment_date=?, appointment_time=?, treatment_type=?, status=?, notes=?
            WHERE id=?
            ''', (patient_id, app_date, app_time, treatment, status, notes, appointment_id))
            
            conn.commit()
            conn.close()
            
            # Refresh appointment list
            self.load_appointments()
            
            messagebox.showinfo("Success", "Appointment updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update appointment: {e}")
            messagebox.showerror("Database Error", f"Failed to update appointment: {str(e)}")

    def delete_appointment(self):
        """Delete selected appointment"""
        selected = self.appointment_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an appointment to delete")
            return
            
        appointment_id = self.appointment_tree.item(selected[0])['values'][0]
        patient_name = self.appointment_tree.item(selected[0])['values'][1]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete appointment for {patient_name}?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete appointment
            cursor.execute('DELETE FROM appointments WHERE id=?', (appointment_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh appointment list
            self.load_appointments()
            
            # Clear form
            self.clear_appointment_form()
            
            messagebox.showinfo("Success", "Appointment deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete appointment: {e}")
            messagebox.showerror("Database Error", f"Failed to delete appointment: {str(e)}")

    def clear_appointment_form(self):
        """Clear appointment form fields"""
        self.app_patient_combo.set('')
        if TK_CALENDAR_AVAILABLE:
            self.app_date_entry.set_date(date.today())
        else:
            self.app_date_entry.delete(0, tk.END)
            self.app_date_entry.insert(0, date.today().isoformat())
        self.app_time_combo.set('')
        self.app_treatment_combo.set('')
        self.app_status_combo.set('Scheduled')
        self.app_notes_text.delete('1.0', tk.END)

    def on_appointment_select(self, event):
        """Load selected appointment data into form"""
        selected = self.appointment_tree.selection()
        if not selected:
            return
            
        # Get selected appointment data
        values = self.appointment_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_appointment_form()
        
        # Fill form with selected appointment data
        # Note: We need to load the full patient details for the combo box
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT p.id, p.full_name FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE a.id = ?', (values[0],))
            patient_data = cursor.fetchone()
            
            if patient_data:
                patient_str = f"{patient_data[0]} - {patient_data[1]}"
                self.app_patient_combo.set(patient_str)
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading patient data: {e}")
        
        # Set other fields
        if len(values) > 2:
            self.app_date_entry.delete(0, tk.END)
            self.app_date_entry.insert(0, values[2])
        if len(values) > 3:
            self.app_time_combo.set(values[3])
        if len(values) > 4:
            self.app_treatment_combo.set(values[4])
        if len(values) > 5:
            self.app_status_combo.set(values[5])
        
        # Load notes
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT notes FROM appointments WHERE id = ?', (values[0],))
            notes_result = cursor.fetchone()
            if notes_result and notes_result[0]:
                self.app_notes_text.insert('1.0', notes_result[0])
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading notes: {e}")

    def filter_appointments(self):
        """Filter appointments by date and status"""
        date_filter = self.app_date_filter.get().strip()
        status_filter = self.app_status_filter.get().strip()
        
        # Clear current items
        for item in self.appointment_tree.get_children():
            self.appointment_tree.delete(item)
            
        # Load appointments from database with filters
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            if date_filter and status_filter != "All":
                cursor.execute('''
                SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, a.treatment_type, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                WHERE a.appointment_date = ? AND a.status = ?
                ORDER BY a.appointment_date, a.appointment_time
                ''', (date_filter, status_filter))
            elif date_filter:
                cursor.execute('''
                SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, a.treatment_type, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                WHERE a.appointment_date = ?
                ORDER BY a.appointment_date, a.appointment_time
                ''', (date_filter,))
            elif status_filter != "All":
                cursor.execute('''
                SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, a.treatment_type, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                WHERE a.status = ?
                ORDER BY a.appointment_date, a.appointment_time
                ''', (status_filter,))
            else:
                cursor.execute('''
                SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, a.treatment_type, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                ORDER BY a.appointment_date, a.appointment_time
                ''')
            
            for row in cursor.fetchall():
                self.appointment_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error filtering appointments: {e}")

    def clear_appointment_filters(self):
        """Clear appointment filters"""
        self.app_date_filter.delete(0, tk.END)
        self.app_date_filter.insert(0, date.today().isoformat())
        self.app_status_filter.set("All")
        self.load_appointments()

    def load_appointments(self):
        """Load appointments from database"""
        try:
            # Clear current items
            for item in self.appointment_tree.get_children():
                self.appointment_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch appointments
            cursor.execute('''
            SELECT a.id, p.full_name, a.appointment_date, a.appointment_time, a.treatment_type, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            ORDER BY a.appointment_date, a.appointment_time
            ''')
            
            # Add appointments to treeview
            for row in cursor.fetchall():
                self.appointment_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading appointments: {e}")

    def create_treatment_tab(self):
        """Create enhanced treatments management tab with blood pressure tracking and X-ray options"""
        try:
            # Create a frame with scrollbar for the form
            form_container = ttk.Frame(self.treatment_frame)
            form_container.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Create a canvas and scrollbar
            canvas = tk.Canvas(form_container)
            scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Treatment form frame
            form_frame = ttk.LabelFrame(scrollable_frame, text="Treatment Information")
            form_frame.pack(fill='x', padx=10, pady=5)
            
            # Form fields
            ttk.Label(form_frame, text="Patient:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.treatment_patient_combo = ttk.Combobox(form_frame, width=27, state="readonly")
            self.treatment_patient_combo.grid(row=0, column=1, sticky='w', padx=5, pady=5)
            self.treatment_patient_combo.bind('<<ComboboxSelected>>', self.on_treatment_patient_select)
            
            ttk.Label(form_frame, text="Date:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            if TK_CALENDAR_AVAILABLE:
                self.treatment_date_entry = DateEntry(form_frame, date_pattern='y-mm-dd', width=27)
            else:
                self.treatment_date_entry = ttk.Entry(form_frame, width=30)
                self.treatment_date_entry.insert(0, date.today().isoformat())
            self.treatment_date_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Treatment Type:*", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.treatment_type_combo = ttk.Combobox(form_frame, values=[""] + self.treatment_types, width=27, state="readonly")
            self.treatment_type_combo.set("")
            self.treatment_type_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            self.treatment_type_combo.bind('<<ComboboxSelected>>', self.on_treatment_type_select)
            
            # RCT Visit selection (only visible for RCT)
            self.rct_visit_label = ttk.Label(form_frame, text="RCT Visit:", font=('Arial', 10, 'bold'))
            self.rct_visit_label.grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.treatment_visit_combo = ttk.Combobox(form_frame, values=[""] + self.rct_visit_options, width=27, state="readonly")
            self.treatment_visit_combo.set("")
            self.treatment_visit_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)
            self.rct_visit_label.grid_remove()  # Hide initially
            self.treatment_visit_combo.grid_remove()  # Hide initially
            
            ttk.Label(form_frame, text="Tooth Number:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.tooth_number_entry = ttk.Entry(form_frame, width=30)
            self.tooth_number_entry.grid(row=4, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Cost (Rs.):", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='e', padx=5, pady=5)
            self.cost_entry = ttk.Entry(form_frame, width=30)
            self.cost_entry.grid(row=5, column=1, sticky='ew', padx=5, pady=5)
            
            # Medical procedure checkboxes and fields
            ttk.Label(form_frame, text="Medical Procedures:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky='ne', padx=5, pady=5)
            
            procedure_frame = ttk.Frame(form_frame)
            procedure_frame.grid(row=6, column=1, sticky='ew', padx=5, pady=5)
            
            self.injection_var = tk.BooleanVar()
            ttk.Checkbutton(procedure_frame, text="Injection Required", variable=self.injection_var).pack(anchor='w')
            
            # Blood pressure fields
            bp_frame = ttk.Frame(procedure_frame)
            bp_frame.pack(anchor='w', pady=2)
            ttk.Label(bp_frame, text="BP Before:").pack(side='left')
            self.bp_before_entry = ttk.Entry(bp_frame, width=10)
            self.bp_before_entry.pack(side='left', padx=5)
            ttk.Label(bp_frame, text="BP After:").pack(side='left', padx=(10, 0))
            self.bp_after_entry = ttk.Entry(bp_frame, width=10)
            self.bp_after_entry.pack(side='left', padx=5)
            
            self.weight_var = tk.BooleanVar()
            ttk.Checkbutton(procedure_frame, text="Weight Checked", variable=self.weight_var).pack(anchor='w')
            
            # X-ray options
            xray_frame = ttk.Frame(procedure_frame)
            xray_frame.pack(anchor='w', pady=2)
            ttk.Label(xray_frame, text="X-Ray:").pack(side='left')
            self.xray_option = ttk.Combobox(xray_frame, values=self.xray_options, width=15, state="readonly")
            self.xray_option.set("Not Taken")
            self.xray_option.pack(side='left', padx=5)
            
            # Zylocin spray option
            self.zylocin_var = tk.BooleanVar()
            ttk.Checkbutton(procedure_frame, text="Zylocin Spray Applied", variable=self.zylocin_var).pack(anchor='w')
            
            ttk.Label(form_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(row=7, column=0, sticky='ne', padx=5, pady=5)
            self.treatment_notes_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
            self.treatment_notes_text.grid(row=7, column=1, sticky='ew', padx=5, pady=5)
            
            form_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=8, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Add Treatment", command=self.add_treatment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update Treatment", command=self.update_treatment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_treatment_form).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Treatment", command=self.delete_treatment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Edit Prices", command=self.edit_treatment_prices).pack(side='left', padx=5)
            
            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Treatment list frame
            list_frame = ttk.LabelFrame(self.treatment_frame, text="Treatment Records")
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # Filter frame
            filter_frame = ttk.Frame(list_frame)
            filter_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(filter_frame, text="Filter by Date:").pack(side='left')
            self.treatment_date_filter = ttk.Entry(filter_frame, width=12)
            self.treatment_date_filter.insert(0, date.today().isoformat())
            self.treatment_date_filter.pack(side='left', padx=5)
            
            ttk.Button(filter_frame, text="Apply Filter", command=self.filter_treatments).pack(side='left', padx=5)
            ttk.Button(filter_frame, text="Clear Filter", command=self.clear_treatment_filters).pack(side='left', padx=5)
            
            # Treeview for treatments with enhanced columns
            columns = ('ID', 'Patient', 'Date', 'Type', 'Visit', 'Tooth', 'Cost', 'BP Before', 'BP After')
            self.treatment_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
            
            col_widths = [50, 120, 80, 100, 80, 60, 80, 80, 80]
            for i, col in enumerate(columns):
                self.treatment_tree.heading(col, text=col)
                self.treatment_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.treatment_tree.yview)
            self.treatment_tree.configure(yscrollcommand=scrollbar.set)
            self.treatment_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind selection event
            self.treatment_tree.bind('<<TreeviewSelect>>', self.on_treatment_select)
            
        except Exception as e:
            self.log_error(f"Error creating treatment tab: {e}")
            raise

    def on_treatment_type_select(self, event):
        """Handle treatment type selection - show RCT visits only for RCT"""
        treatment_type = self.treatment_type_combo.get()
        
        if treatment_type == "RCT":
            self.rct_visit_label.grid()
            self.treatment_visit_combo.grid()
        else:
            self.rct_visit_label.grid_remove()
            self.treatment_visit_combo.grid_remove()
            self.treatment_visit_combo.set("")
        
        # Auto-fill cost
        self.auto_fill_cost()

    def auto_fill_cost(self):
        """Auto-fill cost based on treatment type"""
        treatment_type = self.treatment_type_combo.get()
        if treatment_type in self.treatment_costs:
            self.cost_entry.delete(0, tk.END)
            self.cost_entry.insert(0, str(self.treatment_costs[treatment_type]))

    def edit_treatment_prices(self):
        """Open dialog to edit treatment prices"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Treatment Prices")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create frame for prices
        price_frame = ttk.Frame(dialog)
        price_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create scrollable frame
        canvas = tk.Canvas(price_frame)
        scrollbar = ttk.Scrollbar(price_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add price entries
        price_entries = {}
        row = 0
        for treatment in self.treatment_types:
            ttk.Label(scrollable_frame, text=f"{treatment}:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=5)
            price_var = tk.StringVar(value=str(self.treatment_costs.get(treatment, 0)))
            entry = ttk.Entry(scrollable_frame, textvariable=price_var, width=15)
            entry.grid(row=row, column=1, sticky='w', padx=5, pady=5)
            price_entries[treatment] = price_var
            row += 1
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def save_prices():
            try:
                for treatment, price_var in price_entries.items():
                    price = float(price_var.get())
                    self.treatment_costs[treatment] = price
                
                self.save_treatment_prices()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers for all prices")
        
        ttk.Button(dialog, text="Save Prices", command=save_prices).pack(pady=10)

    def on_treatment_patient_select(self, event):
        """When a patient is selected for treatment, load their recent treatments"""
        patient = self.treatment_patient_combo.get().strip()
        if patient:
            try:
                patient_id = patient.split(' - ')[0]
                conn = sqlite3.connect('dental_practice.db')
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT treatment_type, treatment_date FROM treatments 
                WHERE patient_id = ? 
                ORDER BY treatment_date DESC 
                LIMIT 5
                ''', (patient_id,))
                
                recent_treatments = cursor.fetchall()
                if recent_treatments:
                    # Could display this information somewhere
                    pass
                    
                conn.close()
            except Exception as e:
                self.log_error(f"Error loading patient treatment history: {e}")

    def add_treatment(self):
        """Add a new treatment with enhanced fields"""
        patient = self.treatment_patient_combo.get().strip()
        treatment_date = self.treatment_date_entry.get().strip()
        treatment_type = self.treatment_type_combo.get().strip()
        treatment_visit = self.treatment_visit_combo.get().strip()
        tooth_number = self.tooth_number_entry.get().strip()
        cost = self.cost_entry.get().strip()
        bp_before = self.bp_before_entry.get().strip()
        bp_after = self.bp_after_entry.get().strip()
        notes = self.treatment_notes_text.get('1.0', tk.END).strip()
        
        # Get checkbox values
        injection_required = "Yes" if self.injection_var.get() else "No"
        weight_checked = "Yes" if self.weight_var.get() else "No"
        xray_option = self.xray_option.get()
        zylocin_spray = "Yes" if self.zylocin_var.get() else "No"
        
        # Validate required fields
        if not patient or not treatment_date or not treatment_type:
            messagebox.showerror("Error", "Patient, Date, and Treatment Type are required")
            return
        
        # For RCT, visit is required
        if treatment_type == "RCT" and not treatment_visit:
            messagebox.showerror("Error", "RCT Visit is required for RCT treatments")
            return
        
        # Validate cost
        try:
            cost_value = float(cost) if cost else 0.0
        except ValueError:
            messagebox.showerror("Error", "Cost must be a valid number")
            return
            
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Insert treatment
            cursor.execute('''
            INSERT INTO treatments (patient_id, treatment_date, treatment_type, treatment_visit, tooth_number, cost, 
                                  injection_required, bp_before, bp_after, weight_checked, xray_option, zylocin_spray, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (patient_id, treatment_date, treatment_type, treatment_visit, tooth_number, cost_value,
                  injection_required, bp_before, bp_after, weight_checked, xray_option, zylocin_spray, notes))
            
            conn.commit()
            conn.close()
            
            # Refresh treatment list
            self.load_treatments()
            
            # Clear form
            self.clear_treatment_form()
            
            messagebox.showinfo("Success", "Treatment added successfully")
            
        except Exception as e:
            self.log_error(f"Failed to add treatment: {e}")
            messagebox.showerror("Database Error", f"Failed to add treatment: {str(e)}")

    def update_treatment(self):
        """Update selected treatment with enhanced fields"""
        selected = self.treatment_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a treatment to update")
            return
            
        treatment_id = self.treatment_tree.item(selected[0])['values'][0]
        
        patient = self.treatment_patient_combo.get().strip()
        treatment_date = self.treatment_date_entry.get().strip()
        treatment_type = self.treatment_type_combo.get().strip()
        treatment_visit = self.treatment_visit_combo.get().strip()
        tooth_number = self.tooth_number_entry.get().strip()
        cost = self.cost_entry.get().strip()
        bp_before = self.bp_before_entry.get().strip()
        bp_after = self.bp_after_entry.get().strip()
        notes = self.treatment_notes_text.get('1.0', tk.END).strip()
        
        # Get checkbox values
        injection_required = "Yes" if self.injection_var.get() else "No"
        weight_checked = "Yes" if self.weight_var.get() else "No"
        xray_option = self.xray_option.get()
        zylocin_spray = "Yes" if self.zylocin_var.get() else "No"
        
        # Validate required fields
        if not patient or not treatment_date or not treatment_type:
            messagebox.showerror("Error", "Patient, Date, and Treatment Type are required")
            return
        
        # For RCT, visit is required
        if treatment_type == "RCT" and not treatment_visit:
            messagebox.showerror("Error", "RCT Visit is required for RCT treatments")
            return
        
        # Validate cost
        try:
            cost_value = float(cost) if cost else 0.0
        except ValueError:
            messagebox.showerror("Error", "Cost must be a valid number")
            return
            
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update treatment
            cursor.execute('''
            UPDATE treatments 
            SET patient_id=?, treatment_date=?, treatment_type=?, treatment_visit=?, tooth_number=?, cost=?,
                injection_required=?, bp_before=?, bp_after=?, weight_checked=?, xray_option=?, zylocin_spray=?, notes=?
            WHERE id=?
            ''', (patient_id, treatment_date, treatment_type, treatment_visit, tooth_number, cost_value,
                  injection_required, bp_before, bp_after, weight_checked, xray_option, zylocin_spray, notes, treatment_id))
            
            conn.commit()
            conn.close()
            
            # Refresh treatment list
            self.load_treatments()
            
            messagebox.showinfo("Success", "Treatment updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update treatment: {e}")
            messagebox.showerror("Database Error", f"Failed to update treatment: {str(e)}")

    def delete_treatment(self):
        """Delete selected treatment"""
        selected = self.treatment_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a treatment to delete")
            return
            
        treatment_id = self.treatment_tree.item(selected[0])['values'][0]
        patient_name = self.treatment_tree.item(selected[0])['values'][1]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete treatment for {patient_name}?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete treatment
            cursor.execute('DELETE FROM treatments WHERE id=?', (treatment_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh treatment list
            self.load_treatments()
            
            # Clear form
            self.clear_treatment_form()
            
            messagebox.showinfo("Success", "Treatment deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete treatment: {e}")
            messagebox.showerror("Database Error", f"Failed to delete treatment: {str(e)}")

    def clear_treatment_form(self):
        """Clear treatment form fields"""
        self.treatment_patient_combo.set('')
        if TK_CALENDAR_AVAILABLE:
            self.treatment_date_entry.set_date(date.today())
        else:
            self.treatment_date_entry.delete(0, tk.END)
            self.treatment_date_entry.insert(0, date.today().isoformat())
        self.treatment_type_combo.set('')
        self.treatment_visit_combo.set('')
        self.tooth_number_entry.delete(0, tk.END)
        self.cost_entry.delete(0, tk.END)
        self.injection_var.set(False)
        self.bp_before_entry.delete(0, tk.END)
        self.bp_after_entry.delete(0, tk.END)
        self.weight_var.set(False)
        self.xray_option.set("Not Taken")
        self.zylocin_var.set(False)
        self.treatment_notes_text.delete('1.0', tk.END)
        
        # Hide RCT visit fields
        self.rct_visit_label.grid_remove()
        self.treatment_visit_combo.grid_remove()

    def on_treatment_select(self, event):
        """Load selected treatment data into form"""
        selected = self.treatment_tree.selection()
        if not selected:
            return
            
        # Get selected treatment data
        values = self.treatment_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_treatment_form()
        
        # Fill form with selected treatment data
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT p.id, p.full_name FROM treatments t JOIN patients p ON t.patient_id = p.id WHERE t.id = ?', (values[0],))
            patient_data = cursor.fetchone()
            
            if patient_data:
                patient_str = f"{patient_data[0]} - {patient_data[1]}"
                self.treatment_patient_combo.set(patient_str)
            
            # Load detailed treatment data
            cursor.execute('SELECT * FROM treatments WHERE id = ?', (values[0],))
            treatment_data = cursor.fetchone()
            
            if treatment_data:
                # Set basic fields
                if len(values) > 2:
                    self.treatment_date_entry.delete(0, tk.END)
                    self.treatment_date_entry.insert(0, values[2])
                if len(values) > 3:
                    self.treatment_type_combo.set(values[3])
                    # Show/hide RCT visit fields based on treatment type
                    if values[3] == "RCT":
                        self.rct_visit_label.grid()
                        self.treatment_visit_combo.grid()
                
                # Set additional fields from database
                if treatment_data[4]:  # treatment_visit
                    self.treatment_visit_combo.set(treatment_data[4])
                if treatment_data[5]:  # tooth_number
                    self.tooth_number_entry.insert(0, treatment_data[5])
                if treatment_data[6]:  # cost
                    self.cost_entry.insert(0, str(treatment_data[6]))
                
                # Set medical procedure values
                if treatment_data[7]:  # injection_required
                    self.injection_var.set(treatment_data[7] == "Yes")
                if treatment_data[8]:  # bp_before
                    self.bp_before_entry.insert(0, treatment_data[8])
                if treatment_data[9]:  # bp_after
                    self.bp_after_entry.insert(0, treatment_data[9])
                if treatment_data[10]:  # weight_checked
                    self.weight_var.set(treatment_data[10] == "Yes")
                if treatment_data[11]:  # xray_option
                    self.xray_option.set(treatment_data[11])
                if treatment_data[12]:  # zylocin_spray
                    self.zylocin_var.set(treatment_data[12] == "Yes")
                if treatment_data[13]:  # notes
                    self.treatment_notes_text.insert('1.0', treatment_data[13])
            
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading treatment data: {e}")

    def filter_treatments(self):
        """Filter treatments by date"""
        date_filter = self.treatment_date_filter.get().strip()
        
        # Clear current items
        for item in self.treatment_tree.get_children():
            self.treatment_tree.delete(item)
            
        # Load treatments from database with filter
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            if date_filter:
                cursor.execute('''
                SELECT t.id, p.full_name, t.treatment_date, t.treatment_type, t.treatment_visit, t.tooth_number, t.cost, t.bp_before, t.bp_after
                FROM treatments t
                JOIN patients p ON t.patient_id = p.id
                WHERE t.treatment_date = ?
                ORDER BY t.treatment_date DESC
                ''', (date_filter,))
            else:
                cursor.execute('''
                SELECT t.id, p.full_name, t.treatment_date, t.treatment_type, t.treatment_visit, t.tooth_number, t.cost, t.bp_before, t.bp_after
                FROM treatments t
                JOIN patients p ON t.patient_id = p.id
                ORDER BY t.treatment_date DESC
                ''')
            
            for row in cursor.fetchall():
                self.treatment_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error filtering treatments: {e}")

    def clear_treatment_filters(self):
        """Clear treatment filters"""
        self.treatment_date_filter.delete(0, tk.END)
        self.treatment_date_filter.insert(0, date.today().isoformat())
        self.load_treatments()

    def load_treatments(self):
        """Load treatments from database with enhanced fields"""
        try:
            # Clear current items
            for item in self.treatment_tree.get_children():
                self.treatment_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch treatments with enhanced fields
            cursor.execute('''
            SELECT t.id, p.full_name, t.treatment_date, t.treatment_type, t.treatment_visit, t.tooth_number, t.cost, t.bp_before, t.bp_after
            FROM treatments t
            JOIN patients p ON t.patient_id = p.id
            ORDER BY t.treatment_date DESC
            ''')
            
            # Add treatments to treeview
            for row in cursor.fetchall():
                self.treatment_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading treatments: {e}")

    def create_medical_tab(self):
        """Create medical history tab"""
        try:
            # Medical history frame
            medical_frame = ttk.LabelFrame(self.medical_frame, text="Medical History")
            medical_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Patient selection
            patient_frame = ttk.Frame(medical_frame)
            patient_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(patient_frame, text="Select Patient:").pack(side='left')
            self.medical_patient_combo = ttk.Combobox(patient_frame, width=30, state="readonly")
            self.medical_patient_combo.pack(side='left', padx=5)
            self.medical_patient_combo.bind('<<ComboboxSelected>>', self.load_medical_history)
            
            # Medical history form
            form_frame = ttk.LabelFrame(medical_frame, text="Add Medical Condition")
            form_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Condition:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.condition_entry = ttk.Entry(form_frame, width=30)
            self.condition_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Diagnosis Date:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            if TK_CALENDAR_AVAILABLE:
                self.diagnosis_date_entry = DateEntry(form_frame, date_pattern='y-mm-dd', width=27)
            else:
                self.diagnosis_date_entry = ttk.Entry(form_frame, width=30)
                self.diagnosis_date_entry.insert(0, date.today().isoformat())
            self.diagnosis_date_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Severity:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.severity_combo = ttk.Combobox(form_frame, values=["", "Mild", "Moderate", "Severe"], width=27, state="readonly")
            self.severity_combo.set("")
            self.severity_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='ne', padx=5, pady=5)
            self.medical_notes_text = scrolledtext.ScrolledText(form_frame, width=30, height=3)
            self.medical_notes_text.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
            
            form_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Add Condition", command=self.add_medical_condition).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update Condition", command=self.update_medical_condition).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_medical_form).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Condition", command=self.delete_medical_condition).pack(side='left', padx=5)
            
            # Medical history list
            list_frame = ttk.LabelFrame(medical_frame, text="Medical History Records")
            list_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Treeview for medical history
            columns = ('ID', 'Condition', 'Diagnosis Date', 'Severity', 'Notes')
            self.medical_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
            
            col_widths = [50, 150, 120, 80, 200]
            for i, col in enumerate(columns):
                self.medical_tree.heading(col, text=col)
                self.medical_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.medical_tree.yview)
            self.medical_tree.configure(yscrollcommand=scrollbar.set)
            self.medical_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind selection event
            self.medical_tree.bind('<<TreeviewSelect>>', self.on_medical_select)
            
        except Exception as e:
            self.log_error(f"Error creating medical tab: {e}")
            raise

    def add_medical_condition(self):
        """Add a new medical condition"""
        patient = self.medical_patient_combo.get().strip()
        condition = self.condition_entry.get().strip()
        diagnosis_date = self.diagnosis_date_entry.get().strip()
        severity = self.severity_combo.get().strip()
        notes = self.medical_notes_text.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not patient or not condition:
            messagebox.showerror("Error", "Patient and Condition are required")
            return
            
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Insert medical condition
            cursor.execute('''
            INSERT INTO medical_history (patient_id, condition, diagnosis_date, severity, notes)
            VALUES (?, ?, ?, ?, ?)
            ''', (patient_id, condition, diagnosis_date, severity, notes))
            
            conn.commit()
            conn.close()
            
            # Refresh medical history
            self.load_medical_history()
            
            # Clear form
            self.clear_medical_form()
            
            messagebox.showinfo("Success", "Medical condition added successfully")
            
        except Exception as e:
            self.log_error(f"Failed to add medical condition: {e}")
            messagebox.showerror("Database Error", f"Failed to add medical condition: {str(e)}")

    def update_medical_condition(self):
        """Update selected medical condition"""
        selected = self.medical_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a medical condition to update")
            return
            
        condition_id = self.medical_tree.item(selected[0])['values'][0]
        
        condition = self.condition_entry.get().strip()
        diagnosis_date = self.diagnosis_date_entry.get().strip()
        severity = self.severity_combo.get().strip()
        notes = self.medical_notes_text.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not condition:
            messagebox.showerror("Error", "Condition is required")
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update medical condition
            cursor.execute('''
            UPDATE medical_history 
            SET condition=?, diagnosis_date=?, severity=?, notes=?
            WHERE id=?
            ''', (condition, diagnosis_date, severity, notes, condition_id))
            
            conn.commit()
            conn.close()
            
            # Refresh medical history
            self.load_medical_history()
            
            messagebox.showinfo("Success", "Medical condition updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update medical condition: {e}")
            messagebox.showerror("Database Error", f"Failed to update medical condition: {str(e)}")

    def delete_medical_condition(self):
        """Delete selected medical condition"""
        selected = self.medical_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a medical condition to delete")
            return
            
        condition_id = self.medical_tree.item(selected[0])['values'][0]
        condition_name = self.medical_tree.item(selected[0])['values'][1]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete condition '{condition_name}'?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete medical condition
            cursor.execute('DELETE FROM medical_history WHERE id=?', (condition_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh medical history
            self.load_medical_history()
            
            # Clear form
            self.clear_medical_form()
            
            messagebox.showinfo("Success", "Medical condition deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete medical condition: {e}")
            messagebox.showerror("Database Error", f"Failed to delete medical condition: {str(e)}")

    def clear_medical_form(self):
        """Clear medical form fields"""
        self.condition_entry.delete(0, tk.END)
        if TK_CALENDAR_AVAILABLE:
            self.diagnosis_date_entry.set_date(date.today())
        else:
            self.diagnosis_date_entry.delete(0, tk.END)
            self.diagnosis_date_entry.insert(0, date.today().isoformat())
        self.severity_combo.set("")
        self.medical_notes_text.delete('1.0', tk.END)

    def on_medical_select(self, event):
        """Load selected medical condition data into form"""
        selected = self.medical_tree.selection()
        if not selected:
            return
            
        # Get selected medical condition data
        values = self.medical_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_medical_form()
        
        # Fill form with selected medical condition data
        if len(values) > 1:
            self.condition_entry.insert(0, values[1])
        if len(values) > 2:
            self.diagnosis_date_entry.delete(0, tk.END)
            self.diagnosis_date_entry.insert(0, values[2])
        if len(values) > 3:
            self.severity_combo.set(values[3])
        if len(values) > 4:
            self.medical_notes_text.insert('1.0', values[4])

    def load_medical_history(self, event=None):
        """Load medical history for selected patient"""
        patient = self.medical_patient_combo.get().strip()
        if not patient:
            return
            
        try:
            # Extract patient ID from the combo box value
            patient_id = patient.split(' - ')[0]
            
            # Clear current items
            for item in self.medical_tree.get_children():
                self.medical_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch medical history
            cursor.execute('''
            SELECT id, condition, diagnosis_date, severity, notes
            FROM medical_history
            WHERE patient_id = ?
            ORDER BY diagnosis_date DESC
            ''', (patient_id,))
            
            # Add medical history to treeview
            for row in cursor.fetchall():
                self.medical_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading medical history: {e}")

    def create_expenses_tab(self):
        """Create expenses management tab"""
        try:
            # Expenses frame
            expenses_frame = ttk.LabelFrame(self.expenses_frame, text="Expense Management")
            expenses_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Expense form
            form_frame = ttk.LabelFrame(expenses_frame, text="Add Expense")
            form_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Date:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            if TK_CALENDAR_AVAILABLE:
                self.expense_date = DateEntry(form_frame, date_pattern='y-mm-dd', width=27)
            else:
                self.expense_date = ttk.Entry(form_frame, width=30)
                self.expense_date.insert(0, date.today().isoformat())
            self.expense_date.grid(row=0, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Category:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            self.expense_category = ttk.Combobox(form_frame, values=self.expense_categories, width=27, state="readonly")
            self.expense_category.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Description:*", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.expense_description = ttk.Entry(form_frame, width=30)
            self.expense_description.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Amount (Rs.):*", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.expense_amount = ttk.Entry(form_frame, width=30)
            self.expense_amount.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Payment Method:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.expense_payment = ttk.Combobox(form_frame, values=["Cash", "Bank Transfer", "Cheque", "Card", "Other"], width=27)
            self.expense_payment.set("Cash")
            self.expense_payment.grid(row=4, column=1, sticky='w', padx=5, pady=5)
            
            ttk.Label(form_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='ne', padx=5, pady=5)
            self.expense_notes = scrolledtext.ScrolledText(form_frame, width=30, height=3)
            self.expense_notes.grid(row=5, column=1, sticky='ew', padx=5, pady=5)
            
            form_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=6, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Update Expense", command=self.update_expense).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear Form", command=self.clear_expense_form).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Expense", command=self.delete_expense).pack(side='left', padx=5)
            
            # Expenses list
            list_frame = ttk.LabelFrame(expenses_frame, text="Expense Records")
            list_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Filter frame
            filter_frame = ttk.Frame(list_frame)
            filter_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(filter_frame, text="Filter by Date:").pack(side='left')
            self.expense_date_filter = ttk.Entry(filter_frame, width=12)
            self.expense_date_filter.insert(0, date.today().isoformat())
            self.expense_date_filter.pack(side='left', padx=5)
            
            ttk.Button(filter_frame, text="Apply Filter", command=self.filter_expenses).pack(side='left', padx=5)
            ttk.Button(filter_frame, text="Clear Filter", command=self.clear_expense_filters).pack(side='left', padx=5)
            
            # Treeview for expenses
            columns = ('ID', 'Date', 'Category', 'Description', 'Amount', 'Payment Method')
            self.expense_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
            
            col_widths = [50, 100, 100, 200, 100, 120]
            for i, col in enumerate(columns):
                self.expense_tree.heading(col, text=col)
                self.expense_tree.column(col, width=col_widths[i])
            
            # Scrollbar for treeview
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.expense_tree.yview)
            self.expense_tree.configure(yscrollcommand=scrollbar.set)
            self.expense_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind selection event
            self.expense_tree.bind('<<TreeviewSelect>>', self.on_expense_select)
            
            # Load expenses
            self.load_expenses()
            
        except Exception as e:
            self.log_error(f"Error creating expenses tab: {e}")
            raise

    def add_expense(self):
        """Add a new expense"""
        expense_date = self.expense_date.get().strip()
        category = self.expense_category.get().strip()
        description = self.expense_description.get().strip()
        amount = self.expense_amount.get().strip()
        payment_method = self.expense_payment.get().strip()
        notes = self.expense_notes.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not expense_date or not category or not description or not amount:
            messagebox.showerror("Error", "Date, Category, Description, and Amount are required")
            return
        
        # Validate amount
        try:
            amount_value = float(amount)
            if amount_value <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            messagebox.showerror("Error", "Amount must be a valid positive number")
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Insert expense
            cursor.execute('''
            INSERT INTO expenses (expense_date, category, description, amount, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (expense_date, category, description, amount_value, payment_method, notes))
            
            conn.commit()
            conn.close()
            
            # Refresh expense list
            self.load_expenses()
            
            # Clear form
            self.clear_expense_form()
            
            messagebox.showinfo("Success", "Expense added successfully")
            
        except Exception as e:
            self.log_error(f"Failed to add expense: {e}")
            messagebox.showerror("Database Error", f"Failed to add expense: {str(e)}")

    def update_expense(self):
        """Update selected expense"""
        selected = self.expense_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an expense to update")
            return
            
        expense_id = self.expense_tree.item(selected[0])['values'][0]
        
        expense_date = self.expense_date.get().strip()
        category = self.expense_category.get().strip()
        description = self.expense_description.get().strip()
        amount = self.expense_amount.get().strip()
        payment_method = self.expense_payment.get().strip()
        notes = self.expense_notes.get('1.0', tk.END).strip()
        
        # Validate required fields
        if not expense_date or not category or not description or not amount:
            messagebox.showerror("Error", "Date, Category, Description, and Amount are required")
            return
        
        # Validate amount
        try:
            amount_value = float(amount)
            if amount_value <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            messagebox.showerror("Error", "Amount must be a valid positive number")
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update expense
            cursor.execute('''
            UPDATE expenses 
            SET expense_date=?, category=?, description=?, amount=?, payment_method=?, notes=?
            WHERE id=?
            ''', (expense_date, category, description, amount_value, payment_method, notes, expense_id))
            
            conn.commit()
            conn.close()
            
            # Refresh expense list
            self.load_expenses()
            
            messagebox.showinfo("Success", "Expense updated successfully")
            
        except Exception as e:
            self.log_error(f"Failed to update expense: {e}")
            messagebox.showerror("Database Error", f"Failed to update expense: {str(e)}")

    def delete_expense(self):
        """Delete selected expense"""
        selected = self.expense_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an expense to delete")
            return
            
        expense_id = self.expense_tree.item(selected[0])['values'][0]
        description = self.expense_tree.item(selected[0])['values'][3]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete expense '{description}'?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Delete expense
            cursor.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
            
            conn.commit()
            conn.close()
            
            # Refresh expense list
            self.load_expenses()
            
            # Clear form
            self.clear_expense_form()
            
            messagebox.showinfo("Success", "Expense deleted successfully")
            
        except Exception as e:
            self.log_error(f"Failed to delete expense: {e}")
            messagebox.showerror("Database Error", f"Failed to delete expense: {str(e)}")

    def clear_expense_form(self):
        """Clear expense form fields"""
        if TK_CALENDAR_AVAILABLE:
            self.expense_date.set_date(date.today())
        else:
            self.expense_date.delete(0, tk.END)
            self.expense_date.insert(0, date.today().isoformat())
        self.expense_category.set('')
        self.expense_description.delete(0, tk.END)
        self.expense_amount.delete(0, tk.END)
        self.expense_payment.set('Cash')
        self.expense_notes.delete('1.0', tk.END)

    def on_expense_select(self, event):
        """Load selected expense data into form"""
        selected = self.expense_tree.selection()
        if not selected:
            return
            
        # Get selected expense data
        values = self.expense_tree.item(selected[0])['values']
        
        # Clear form first
        self.clear_expense_form()
        
        # Fill form with selected expense data
        if len(values) > 1:
            self.expense_date.delete(0, tk.END)
            self.expense_date.insert(0, values[1])
        if len(values) > 2:
            self.expense_category.set(values[2])
        if len(values) > 3:
            self.expense_description.insert(0, values[3])
        if len(values) > 4:
            self.expense_amount.insert(0, str(values[4]))
        if len(values) > 5:
            self.expense_payment.set(values[5])
        
        # Load notes
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT notes FROM expenses WHERE id = ?', (values[0],))
            notes_result = cursor.fetchone()
            if notes_result and notes_result[0]:
                self.expense_notes.insert('1.0', notes_result[0])
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading expense notes: {e}")

    def filter_expenses(self):
        """Filter expenses by date"""
        date_filter = self.expense_date_filter.get().strip()
        
        # Clear current items
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)
            
        # Load expenses from database with filter
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            if date_filter:
                cursor.execute('''
                SELECT id, expense_date, category, description, amount, payment_method
                FROM expenses
                WHERE expense_date = ?
                ORDER BY expense_date DESC
                ''', (date_filter,))
            else:
                cursor.execute('''
                SELECT id, expense_date, category, description, amount, payment_method
                FROM expenses
                ORDER BY expense_date DESC
                ''')
            
            for row in cursor.fetchall():
                self.expense_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error filtering expenses: {e}")

    def clear_expense_filters(self):
        """Clear expense filters"""
        self.expense_date_filter.delete(0, tk.END)
        self.expense_date_filter.insert(0, date.today().isoformat())
        self.load_expenses()

    def load_expenses(self):
        """Load expenses from database"""
        try:
            # Clear current items
            for item in self.expense_tree.get_children():
                self.expense_tree.delete(item)
                
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Fetch expenses
            cursor.execute('''
            SELECT id, expense_date, category, description, amount, payment_method
            FROM expenses
            ORDER BY expense_date DESC
            ''')
            
            # Add expenses to treeview
            for row in cursor.fetchall():
                self.expense_tree.insert('', 'end', values=row)
                
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading expenses: {e}")

    def create_reports_tab(self):
        """Create enhanced reports and analytics tab with expense tracking"""
        try:
            # Reports frame
            reports_frame = ttk.LabelFrame(self.reports_frame, text="Reports and Analytics")
            reports_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Report type selection
            report_frame = ttk.Frame(reports_frame)
            report_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(report_frame, text="Report Type:").pack(side='left')
            self.report_type = ttk.Combobox(report_frame, values=[
                "Patient Statistics", 
                "Appointment Summary", 
                "Treatment Revenue", 
                "Expense Report",
                "Profit & Loss",
                "Monthly Report"
            ], width=20, state="readonly")
            self.report_type.set("Patient Statistics")
            self.report_type.pack(side='left', padx=5)
            
            ttk.Label(report_frame, text="Start Date:").pack(side='left', padx=(20, 5))
            if TK_CALENDAR_AVAILABLE:
                self.report_start_date = DateEntry(report_frame, date_pattern='y-mm-dd', width=12)
            else:
                self.report_start_date = ttk.Entry(report_frame, width=12)
                self.report_start_date.insert(0, (date.today() - timedelta(days=30)).isoformat())
            self.report_start_date.pack(side='left', padx=5)
            
            ttk.Label(report_frame, text="End Date:").pack(side='left', padx=(20, 5))
            if TK_CALENDAR_AVAILABLE:
                self.report_end_date = DateEntry(report_frame, date_pattern='y-mm-dd', width=12)
            else:
                self.report_end_date = ttk.Entry(report_frame, width=12)
                self.report_end_date.insert(0, date.today().isoformat())
            self.report_end_date.pack(side='left', padx=5)
            
            ttk.Button(report_frame, text="Generate Report", command=self.generate_report).pack(side='left', padx=5)
            ttk.Button(report_frame, text="Export to CSV", command=self.export_report).pack(side='left', padx=5)
            ttk.Button(report_frame, text="Generate Chart", command=self.generate_chart_report).pack(side='left', padx=5)
            
            # Report display area
            self.report_text = scrolledtext.ScrolledText(reports_frame, width=80, height=20)
            self.report_text.pack(fill='both', expand=True, padx=5, pady=5)
            
        except Exception as e:
            self.log_error(f"Error creating reports tab: {e}")
            raise

    def generate_report(self):
        """Generate selected report with expense tracking"""
        report_type = self.report_type.get()
        start_date = self.report_start_date.get().strip()
        end_date = self.report_end_date.get().strip()
        
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            report_content = f"Report: {report_type}\n"
            report_content += f"Period: {start_date} to {end_date}\n"
            report_content += "="*50 + "\n\n"
            
            if report_type == "Patient Statistics":
                # Total patients
                cursor.execute('SELECT COUNT(*) FROM patients WHERE registration_date BETWEEN ? AND ?', (start_date, end_date))
                total_patients = cursor.fetchone()[0]
                report_content += f"Total Patients Registered: {total_patients}\n\n"
                
                # Patients by gender
                cursor.execute('SELECT gender, COUNT(*) FROM patients WHERE registration_date BETWEEN ? AND ? GROUP BY gender', (start_date, end_date))
                report_content += "Patients by Gender:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0] or 'Not specified'}: {row[1]}\n"
                report_content += "\n"
                
                # Patients by city
                cursor.execute('SELECT city, COUNT(*) FROM patients WHERE registration_date BETWEEN ? AND ? GROUP BY city', (start_date, end_date))
                report_content += "Patients by City:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0] or 'Not specified'}: {row[1]}\n"
                report_content += "\n"
                
                # Patients by village
                cursor.execute('SELECT village, COUNT(*) FROM patients WHERE registration_date BETWEEN ? AND ? GROUP BY village', (start_date, end_date))
                report_content += "Patients by Village:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0] or 'Not specified'}: {row[1]}\n"
                
            elif report_type == "Appointment Summary":
                # Appointment statistics
                cursor.execute('''
                SELECT status, COUNT(*) 
                FROM appointments 
                WHERE appointment_date BETWEEN ? AND ? 
                GROUP BY status
                ''', (start_date, end_date))
                report_content += "Appointments by Status:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[1]}\n"
                report_content += "\n"
                
                # Appointments by treatment type
                cursor.execute('''
                SELECT treatment_type, COUNT(*) 
                FROM appointments 
                WHERE appointment_date BETWEEN ? AND ? 
                GROUP BY treatment_type
                ''', (start_date, end_date))
                report_content += "Appointments by Treatment Type:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[1]}\n"
                
            elif report_type == "Treatment Revenue":
                # Total revenue
                cursor.execute('SELECT SUM(cost) FROM treatments WHERE treatment_date BETWEEN ? AND ?', (start_date, end_date))
                total_revenue = cursor.fetchone()[0] or 0
                report_content += f"Total Revenue: Rs. {total_revenue:,.2f}\n\n"
                
                # Revenue by treatment type
                cursor.execute('''
                SELECT treatment_type, SUM(cost), COUNT(*) 
                FROM treatments 
                WHERE treatment_date BETWEEN ? AND ? 
                GROUP BY treatment_type
                ORDER BY SUM(cost) DESC
                ''', (start_date, end_date))
                report_content += "Revenue by Treatment Type:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[2]} treatments, Rs. {row[1]:,.2f}\n"
                report_content += "\n"
                
                # Top patients by revenue
                cursor.execute('''
                SELECT p.full_name, SUM(t.cost) as total_spent
                FROM treatments t
                JOIN patients p ON t.patient_id = p.id
                WHERE t.treatment_date BETWEEN ? AND ?
                GROUP BY p.id
                ORDER BY total_spent DESC
                LIMIT 10
                ''', (start_date, end_date))
                report_content += "Top Patients by Revenue:\n"
                for i, row in enumerate(cursor.fetchall(), 1):
                    report_content += f"  {i}. {row[0]}: Rs. {row[1]:,.2f}\n"
                
            elif report_type == "Expense Report":
                # Total expenses
                cursor.execute('SELECT SUM(amount) FROM expenses WHERE expense_date BETWEEN ? AND ?', (start_date, end_date))
                total_expenses = cursor.fetchone()[0] or 0
                report_content += f"Total Expenses: Rs. {total_expenses:,.2f}\n\n"
                
                # Expenses by category
                cursor.execute('''
                SELECT category, SUM(amount), COUNT(*) 
                FROM expenses 
                WHERE expense_date BETWEEN ? AND ? 
                GROUP BY category
                ORDER BY SUM(amount) DESC
                ''', (start_date, end_date))
                report_content += "Expenses by Category:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[2]} expenses, Rs. {row[1]:,.2f}\n"
                
            elif report_type == "Profit & Loss":
                # Total revenue
                cursor.execute('SELECT SUM(cost) FROM treatments WHERE treatment_date BETWEEN ? AND ?', (start_date, end_date))
                total_revenue = cursor.fetchone()[0] or 0
                
                # Total expenses
                cursor.execute('SELECT SUM(amount) FROM expenses WHERE expense_date BETWEEN ? AND ?', (start_date, end_date))
                total_expenses = cursor.fetchone()[0] or 0
                
                profit_loss = total_revenue - total_expenses
                
                report_content += f"Total Revenue: Rs. {total_revenue:,.2f}\n"
                report_content += f"Total Expenses: Rs. {total_expenses:,.2f}\n"
                report_content += f"Net {'Profit' if profit_loss >= 0 else 'Loss'}: Rs. {abs(profit_loss):,.2f}\n\n"
                
                # Revenue by treatment type
                cursor.execute('''
                SELECT treatment_type, SUM(cost), COUNT(*) 
                FROM treatments 
                WHERE treatment_date BETWEEN ? AND ? 
                GROUP BY treatment_type
                ORDER BY SUM(cost) DESC
                ''', (start_date, end_date))
                report_content += "Revenue by Treatment Type:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[2]} treatments, Rs. {row[1]:,.2f}\n"
                
                report_content += "\nExpenses by Category:\n"
                cursor.execute('''
                SELECT category, SUM(amount), COUNT(*) 
                FROM expenses 
                WHERE expense_date BETWEEN ? AND ? 
                GROUP BY category
                ORDER BY SUM(amount) DESC
                ''', (start_date, end_date))
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: {row[2]} expenses, Rs. {row[1]:,.2f}\n"
                
            elif report_type == "Monthly Report":
                # Comprehensive monthly report with expenses
                cursor.execute('SELECT COUNT(*) FROM patients WHERE registration_date BETWEEN ? AND ?', (start_date, end_date))
                new_patients = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM appointments WHERE appointment_date BETWEEN ? AND ?', (start_date, end_date))
                total_appointments = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM appointments WHERE appointment_date BETWEEN ? AND ? AND status = "Completed"', (start_date, end_date))
                completed_appointments = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(cost) FROM treatments WHERE treatment_date BETWEEN ? AND ?', (start_date, end_date))
                total_revenue = cursor.fetchone()[0] or 0
                
                cursor.execute('SELECT SUM(amount) FROM expenses WHERE expense_date BETWEEN ? AND ?', (start_date, end_date))
                total_expenses = cursor.fetchone()[0] or 0
                
                profit_loss = total_revenue - total_expenses
                
                report_content += f"New Patients: {new_patients}\n"
                report_content += f"Total Appointments: {total_appointments}\n"
                report_content += f"Completed Appointments: {completed_appointments}\n"
                report_content += f"Total Revenue: Rs. {total_revenue:,.2f}\n"
                report_content += f"Total Expenses: Rs. {total_expenses:,.2f}\n"
                report_content += f"Net {'Profit' if profit_loss >= 0 else 'Loss'}: Rs. {abs(profit_loss):,.2f}\n\n"
                
                # Daily revenue and expense trend
                cursor.execute('''
                SELECT treatment_date, SUM(cost)
                FROM treatments
                WHERE treatment_date BETWEEN ? AND ?
                GROUP BY treatment_date
                ORDER BY treatment_date
                ''', (start_date, end_date))
                report_content += "Daily Revenue Trend:\n"
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: Rs. {row[1]:,.2f}\n"
                
                report_content += "\nDaily Expense Trend:\n"
                cursor.execute('''
                SELECT expense_date, SUM(amount)
                FROM expenses
                WHERE expense_date BETWEEN ? AND ?
                GROUP BY expense_date
                ORDER BY expense_date
                ''', (start_date, end_date))
                for row in cursor.fetchall():
                    report_content += f"  {row[0]}: Rs. {row[1]:,.2f}\n"
            
            conn.close()
            
            # Display report
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', report_content)
            
        except Exception as e:
            self.log_error(f"Failed to generate report: {e}")
            messagebox.showerror("Report Error", f"Failed to generate report: {str(e)}")

    def generate_chart_report(self):
        """Generate chart report"""
        try:
            start_date = self.report_start_date.get().strip()
            end_date = self.report_end_date.get().strip()
            
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Monthly revenue data for chart
            cursor.execute('''
            SELECT strftime('%Y-%m', treatment_date) as month, SUM(cost)
            FROM treatments
            WHERE treatment_date BETWEEN ? AND ?
            GROUP BY month
            ORDER BY month
            ''', (start_date, end_date))
            
            revenue_data = cursor.fetchall()
            
            # Monthly expense data for chart
            cursor.execute('''
            SELECT strftime('%Y-%m', expense_date) as month, SUM(amount)
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY month
            ORDER BY month
            ''', (start_date, end_date))
            
            expense_data = cursor.fetchall()
            
            if not revenue_data and not expense_data:
                messagebox.showinfo("No Data", "No data available for the selected period")
                return
            
            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title("Financial Chart")
            chart_window.geometry("800x600")
            
            # Create matplotlib figure
            fig = Figure(figsize=(8, 6))
            ax = fig.add_subplot(111)
            
            months = [row[0] for row in revenue_data] if revenue_data else [row[0] for row in expense_data]
            revenues = [row[1] for row in revenue_data] if revenue_data else [0] * len(months)
            expenses = [row[1] for row in expense_data] if expense_data else [0] * len(months)
            
            # Ensure both lists have the same length
            if len(revenues) < len(months):
                revenues.extend([0] * (len(months) - len(revenues)))
            if len(expenses) < len(months):
                expenses.extend([0] * (len(months) - len(expenses)))
            
            width = 0.35
            x = range(len(months))
            
            ax.bar([i - width/2 for i in x], revenues, width, label='Revenue', color='green')
            ax.bar([i + width/2 for i in x], expenses, width, label='Expenses', color='red')
            
            ax.set_title('Monthly Revenue vs Expenses')
            ax.set_xlabel('Month')
            ax.set_ylabel('Amount (Rs.)')
            ax.set_xticks(x)
            ax.set_xticklabels(months, rotation=45)
            ax.legend()
            
            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, chart_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
            conn.close()
            
        except Exception as e:
            self.log_error(f"Failed to generate chart: {e}")
            messagebox.showerror("Chart Error", f"Failed to generate chart: {str(e)}")

    def export_report(self):
        """Export current report to CSV"""
        report_content = self.report_text.get('1.0', tk.END).strip()
        if not report_content:
            messagebox.showwarning("Export", "No report content to export")
            return
            
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as file:
                    # For simplicity, export as plain text
                    file.write(report_content)
                messagebox.showinfo("Export Successful", f"Report exported to {filename}")
        except Exception as e:
            self.log_error(f"Failed to export report: {e}")
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")

    def create_settings_tab(self):
        """Create settings tab for clinic configuration"""
        try:
            # Settings frame
            settings_frame = ttk.LabelFrame(self.settings_frame, text="Clinic Settings")
            settings_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Create a canvas and scrollbar for settings
            canvas = tk.Canvas(settings_frame)
            scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Clinic information
            clinic_info_frame = ttk.LabelFrame(scrollable_frame, text="Clinic Information")
            clinic_info_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Label(clinic_info_frame, text="Clinic Name:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='e', padx=5, pady=5)
            self.settings_clinic_name = ttk.Entry(clinic_info_frame, width=40)
            self.settings_clinic_name.insert(0, self.clinic_name)
            self.settings_clinic_name.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(clinic_info_frame, text="Welcome Message:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='e', padx=5, pady=5)
            self.settings_welcome_msg = ttk.Entry(clinic_info_frame, width=40)
            self.settings_welcome_msg.insert(0, self.welcome_message)
            self.settings_welcome_msg.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(clinic_info_frame, text="Address:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='e', padx=5, pady=5)
            self.settings_address = ttk.Entry(clinic_info_frame, width=40)
            self.settings_address.insert(0, self.clinic_address)
            self.settings_address.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(clinic_info_frame, text="Phone:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='e', padx=5, pady=5)
            self.settings_phone = ttk.Entry(clinic_info_frame, width=40)
            self.settings_phone.insert(0, self.clinic_phone)
            self.settings_phone.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(clinic_info_frame, text="Email:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='e', padx=5, pady=5)
            self.settings_email = ttk.Entry(clinic_info_frame, width=40)
            self.settings_email.insert(0, self.clinic_email)
            self.settings_email.grid(row=4, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(clinic_info_frame, text="Logo Path:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='e', padx=5, pady=5)
            logo_frame = ttk.Frame(clinic_info_frame)
            logo_frame.grid(row=5, column=1, sticky='ew', padx=5, pady=5)
            self.settings_logo_path = ttk.Entry(logo_frame, width=30)
            self.settings_logo_path.insert(0, self.logo_path)
            self.settings_logo_path.pack(side='left', fill='x', expand=True)
            ttk.Button(logo_frame, text="Browse", command=self.browse_logo).pack(side='right', padx=5)
            
            clinic_info_frame.columnconfigure(1, weight=1)
            
            # Customizable lists
            lists_frame = ttk.LabelFrame(scrollable_frame, text="Customizable Lists")
            lists_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Label(lists_frame, text="Cities (one per line):", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='ne', padx=5, pady=5)
            self.settings_cities = scrolledtext.ScrolledText(lists_frame, width=30, height=5)
            self.settings_cities.insert('1.0', '\n'.join(self.cities))
            self.settings_cities.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(lists_frame, text="Areas (one per line):", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='ne', padx=5, pady=5)
            self.settings_areas = scrolledtext.ScrolledText(lists_frame, width=30, height=5)
            self.settings_areas.insert('1.0', '\n'.join(self.areas))
            self.settings_areas.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(lists_frame, text="Villages (one per line):", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='ne', padx=5, pady=5)
            self.settings_villages = scrolledtext.ScrolledText(lists_frame, width=30, height=5)
            self.settings_villages.insert('1.0', '\n'.join(self.villages))
            self.settings_villages.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
            
            ttk.Label(lists_frame, text="Treatment Types (one per line):", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='ne', padx=5, pady=5)
            self.settings_treatments = scrolledtext.ScrolledText(lists_frame, width=30, height=5)
            self.settings_treatments.insert('1.0', '\n'.join(self.treatment_types))
            self.settings_treatments.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
            
            lists_frame.columnconfigure(1, weight=1)
            
            # Backup and restore section
            backup_frame = ttk.LabelFrame(scrollable_frame, text="Backup & Restore")
            backup_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Button(backup_frame, text="Backup Database", command=self.backup_database).pack(side='left', padx=5)
            ttk.Button(backup_frame, text="Restore Database", command=self.restore_database).pack(side='left', padx=5)
            ttk.Button(backup_frame, text="Export All Data", command=self.export_all_data).pack(side='left', padx=5)
            ttk.Button(backup_frame, text="Optimize Database", command=self.optimize_database).pack(side='left', padx=5)
            
            # Button frame
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill='x', padx=10, pady=10)
            
            ttk.Button(button_frame, text="Save Settings", command=self.save_settings).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_settings).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Reload Settings", command=self.reload_settings).pack(side='left', padx=5)
            
            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            self.log_error(f"Error creating settings tab: {e}")
            raise

    def optimize_database(self):
        """Optimize database performance"""
        try:
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Vacuum database
            cursor.execute('VACUUM')
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Optimization Complete", "Database optimization completed successfully")
        except Exception as e:
            self.log_error(f"Database optimization failed: {e}")
            messagebox.showerror("Optimization Error", f"Failed to optimize database: {str(e)}")

    def browse_logo(self):
        """Browse for logo image file"""
        filename = filedialog.askopenfilename(
            title="Select Logo Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.settings_logo_path.delete(0, tk.END)
            self.settings_logo_path.insert(0, filename)

    def save_settings(self):
        """Save clinic settings to database"""
        try:
            clinic_name = self.settings_clinic_name.get().strip()
            welcome_msg = self.settings_welcome_msg.get().strip()
            address = self.settings_address.get().strip()
            phone = self.settings_phone.get().strip()
            email = self.settings_email.get().strip()
            logo_path = self.settings_logo_path.get().strip()
            
            # Validate required field
            if not clinic_name:
                messagebox.showerror("Error", "Clinic Name is required")
                return
            
            # Validate email if provided
            if email and not self.validate_email(email):
                messagebox.showerror("Error", "Invalid email format")
                return
            
            # Get list values
            cities = self.settings_cities.get('1.0', tk.END).strip().split('\n')
            areas = self.settings_areas.get('1.0', tk.END).strip().split('\n')
            villages = self.settings_villages.get('1.0', tk.END).strip().split('\n')
            treatments = self.settings_treatments.get('1.0', tk.END).strip().split('\n')
            
            # Remove empty strings
            cities = [city for city in cities if city]
            areas = [area for area in areas if area]
            villages = [village for village in villages if village]
            treatments = [treatment for treatment in treatments if treatment]
            
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Update settings
            cursor.execute('''
            UPDATE settings 
            SET clinic_name=?, welcome_message=?, address=?, phone=?, email=?, logo_path=?,
                cities=?, areas=?, villages=?, treatment_types=?
            WHERE id=1
            ''', (clinic_name, welcome_msg, address, phone, email, logo_path,
                  save_json_setting(cities), save_json_setting(areas), 
                  save_json_setting(villages), save_json_setting(treatments)))
            
            conn.commit()
            conn.close()
            
            # Reload settings
            self.load_settings()
            
            messagebox.showinfo("Success", "Settings saved successfully")
            
        except Exception as e:
            self.log_error(f"Failed to save settings: {e}")
            messagebox.showerror("Database Error", f"Failed to save settings: {str(e)}")

    def reset_settings(self):
        """Reset settings to default values"""
        if not messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all settings to default values?"):
            return
            
        try:
            # Connect to database
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Reset settings to defaults
            cursor.execute('''
            UPDATE settings 
            SET clinic_name=?, welcome_message=?, address=?, phone=?, email=?, logo_path=?,
                cities=?, areas=?, villages=?, treatment_types=?
            WHERE id=1
            ''', ('Khurshid Dental Clinic Khuzdar', 'Welcome to our Dental Clinic', 
                  'Khuzdar, Balochistan', '', '', '',
                  save_json_setting(["Khuzdar", "Karachi", "Quetta", "Islamabad", "Lahore", "Other"]),
                  save_json_setting(["City Center", "Gulshan-e-Khuwaja", "Mughalabad", "Sariab", "Other"]),
                  save_json_setting(["Nall", "Zidi", "Mola", "Karkh", "Surab", "Zehri", "Wadh", "Besima", "Sasol", "Baghban", "Other"]),
                  save_json_setting(["Checkup", "Cleaning", "Filling", "RCT", "Extraction", "Crown", "Bridge", "Dentures", "Whitening", "Zylocin Spray"])))
            
            conn.commit()
            conn.close()
            
            # Reload settings and refresh the form
            self.reload_settings()
            
            messagebox.showinfo("Success", "Settings reset to default values")
            
        except Exception as e:
            self.log_error(f"Failed to reset settings: {e}")
            messagebox.showerror("Database Error", f"Failed to reset settings: {str(e)}")

    def reload_settings(self):
        """Reload settings from database and refresh the form"""
        self.load_settings()
        
        # Update form fields
        self.settings_clinic_name.delete(0, tk.END)
        self.settings_clinic_name.insert(0, self.clinic_name)
        
        self.settings_welcome_msg.delete(0, tk.END)
        self.settings_welcome_msg.insert(0, self.welcome_message)
        
        self.settings_address.delete(0, tk.END)
        self.settings_address.insert(0, self.clinic_address)
        
        self.settings_phone.delete(0, tk.END)
        self.settings_phone.insert(0, self.clinic_phone)
        
        self.settings_email.delete(0, tk.END)
        self.settings_email.insert(0, self.clinic_email)
        
        self.settings_logo_path.delete(0, tk.END)
        self.settings_logo_path.insert(0, self.logo_path)
        
        self.settings_cities.delete('1.0', tk.END)
        self.settings_cities.insert('1.0', '\n'.join(self.cities))
        
        self.settings_areas.delete('1.0', tk.END)
        self.settings_areas.insert('1.0', '\n'.join(self.areas))
        
        self.settings_villages.delete('1.0', tk.END)
        self.settings_villages.insert('1.0', '\n'.join(self.villages))
        
        self.settings_treatments.delete('1.0', tk.END)
        self.settings_treatments.insert('1.0', '\n'.join(self.treatment_types))

    def load_initial_data(self):
        """Load initial data for combo boxes and lists"""
        try:
            # Load patients for combo boxes
            conn = sqlite3.connect('dental_practice.db')
            cursor = conn.cursor()
            
            # Load patients for appointment tab
            cursor.execute('SELECT id, full_name FROM patients ORDER BY full_name')
            patients = cursor.fetchall()
            patient_list = [f"{row[0]} - {row[1]}" for row in patients]
            
            self.app_patient_combo['values'] = patient_list
            self.treatment_patient_combo['values'] = patient_list
            self.medical_patient_combo['values'] = patient_list
            
            # Load initial data for each tab
            self.load_patients()
            self.load_appointments()
            self.load_treatments()
            self.load_expenses()
            
            # Refresh dashboard
            self.refresh_dashboard()
            
            conn.close()
            
        except Exception as e:
            self.log_error(f"Error loading initial data: {e}")

    def auto_refresh_dashboard(self):
        """Auto-refresh dashboard every 30 seconds"""
        self.refresh_dashboard()
        self.root.after(30000, self.auto_refresh_dashboard)  # Refresh every 30 seconds

def main():
    """Main function to run the application"""
    try:
        root = tk.Tk()
        app = DentalPracticeApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")

if __name__ == "__main__":
    main()