from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from database import get_connection, initialize_database
import sqlite3
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
import os

app = Flask(__name__)

# Initialize database on startup
initialize_database()

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/')
def index():
    """Home page dashboard"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get summary data
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Income'")
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Expense'")
    total_expenses = cursor.fetchone()[0] or 0
    
    balance = total_income - total_expenses
    
    # Get recent transactions
    cursor.execute("SELECT id, type, category, amount, date FROM transactions ORDER BY date DESC LIMIT 5")
    recent_transactions = cursor.fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         total_income=total_income,
                         total_expenses=total_expenses,
                         balance=balance,
                         recent_transactions=recent_transactions)

@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    if request.method == 'POST':
        category = request.form['category']
        amount = float(request.form['amount'])
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (type, category, amount) VALUES (?, ?, ?)", 
                     ("Income", category, amount))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
    
    return render_template('add_income.html')

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if request.method == 'POST':
        category = request.form['category']
        amount = float(request.form['amount'])
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (type, category, amount) VALUES (?, ?, ?)", 
                     ("Expense", category, amount))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
    
    return render_template('add_expense.html')

@app.route('/summary')
def summary():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT type, category, amount, date FROM transactions ORDER BY date DESC")
    transactions = cursor.fetchall()
    
    # Get income by category
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE type = 'Income' GROUP BY category")
    income_by_category = cursor.fetchall()
    
    # Get expenses by category
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE type = 'Expense' GROUP BY category")
    expense_by_category = cursor.fetchall()
    
    # Get totals
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Income'")
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Expense'")
    total_expenses = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return render_template('summary.html',
                         transactions=transactions,
                         income_by_category=income_by_category,
                         expense_by_category=expense_by_category,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         balance=total_income - total_expenses)

@app.route('/savings', methods=['GET', 'POST'])
def savings():
    conn = get_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        goal_amount = float(request.form['goal_amount'])
        cursor.execute("INSERT OR REPLACE INTO savings_goal (id, goal_amount) VALUES (1, ?)", (goal_amount,))
        conn.commit()
    
    # Get current goal
    cursor.execute("SELECT goal_amount FROM savings_goal WHERE id = 1")
    goal = cursor.fetchone()
    goal_amount = goal[0] if goal else 0
    
    # Get current balance
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Income'")
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'Expense'")
    total_expenses = cursor.fetchone()[0] or 0
    
    balance = total_income - total_expenses
    progress = (balance / goal_amount * 100) if goal_amount > 0 else 0
    
    conn.close()
    
    return render_template('savings.html', 
                         goal_amount=goal_amount,
                         balance=balance,
                         progress=min(progress, 100))

@app.route('/visualizations')
def visualizations():
    # Generate expense bar chart
    bar_chart = generate_bar_chart()
    pie_chart = generate_pie_chart()
    
    return render_template('visualizations.html', 
                         bar_chart=bar_chart,
                         pie_chart=pie_chart)

def generate_bar_chart():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE type = 'Expense' GROUP BY category")
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        categories = [row[0] for row in rows]
        amounts = [row[1] for row in rows]
        
        plt.figure(figsize=(10, 6))
        plt.bar(categories, amounts, color='skyblue')
        plt.xlabel('Category')
        plt.ylabel('Amount (₹)')
        plt.title('Spending by Category')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Convert to base64 for embedding in HTML
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()
        
        return plot_url
    return None

def generate_pie_chart():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE type = 'Expense' GROUP BY category")
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        categories = [row[0] for row in rows]
        amounts = [row[1] for row in rows]
        
        plt.figure(figsize=(8, 8))
        plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90)
        plt.title('Spending Distribution')
        plt.tight_layout()
        
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()
        
        return plot_url
    return None

@app.route('/api/delete_transaction/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)