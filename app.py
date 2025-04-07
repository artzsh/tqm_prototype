from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
import io
import pandas as pd
from datetime import datetime
from openpyxl.utils import get_column_letter


app = Flask(__name__)
app.secret_key = 'secretkey'

# ------------------------
# Пример данных пользователей (пока остаются в памяти)
# ------------------------
users = {
    'employee': 'password123'
}

# ------------------------
# Функция для получения подключения к базе данных
# ------------------------
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="postgres",
        user="postgres",
        password="123",
        options="-c search_path=prototype"
    )
    return conn


# ------------------------
# Функция проверки авторизации
# ------------------------
def login_required(func):
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            flash('Пожалуйста, авторизуйтесь', 'warning')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# ------------------------
# Маршруты
# ------------------------
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('choose_batch'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and users[username] == password:
            session['username'] = username
            flash('Успешная авторизация!', 'success')
            return redirect(url_for('choose_batch'))
        else:
            flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

# ------------------------
# Выбор партии
# ------------------------
@app.route('/choose_batch', methods=['GET', 'POST'])
@login_required
def choose_batch():
    selected_date = None
    batches = None
    if request.method == 'POST':
        input_date = request.form.get('batch_date')
        selected_date = input_date
        if not input_date:
            flash('Введите дату', 'warning')
            return redirect(url_for('choose_batch'))
        
        # Если пользователь ещё не выбрал партию, а только ввёл дату
        if not request.form.get('batch_id'):
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT * FROM batches 
                WHERE final_control_done = FALSE AND batch_date = %s
                ORDER BY batch_date
            """, (input_date,))
            batches = cur.fetchall()
            cur.close()
            conn.close()
            if not batches:
                flash('Нет партий для выбранной даты', 'info')
            # Возвращаем форму с датой и, если найдены, со списком партий
            return render_template('choose_batch.html', batches=batches, selected_date=selected_date)
        else:
            # Если партия выбрана, переходим к паспорту изделия
            selected_batch_id = request.form.get('batch_id')
            return redirect(url_for('passport_view', batch_id=selected_batch_id))
    
    # При GET-запросе выводим форму без списка партий
    return render_template('choose_batch.html', batches=batches, selected_date=selected_date)



# ------------------------
# Паспорт изделия и ввод результатов финального контроля
# ------------------------
@app.route('/passport/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def passport_view(batch_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Получаем данные партии
    cur.execute("SELECT * FROM batches WHERE id = %s", (batch_id,))
    batch = cur.fetchone()
    if not batch:
        flash('Партия не найдена', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('choose_batch'))
    
    # Получаем данные технологических этапов
    cur.execute("SELECT * FROM smelting_data WHERE batch_id = %s", (batch_id,))
    batch['smelting_data'] = cur.fetchone()
    cur.execute("SELECT * FROM refining_data WHERE batch_id = %s", (batch_id,))
    batch['refining_data'] = cur.fetchone()
    cur.execute("SELECT * FROM cooling_data WHERE batch_id = %s", (batch_id,))
    batch['cooling_data'] = cur.fetchone()
    cur.execute("SELECT * FROM heat_treatment_data WHERE batch_id = %s", (batch_id,))
    batch['heat_treatment_data'] = cur.fetchone()
    cur.execute("SELECT * FROM mechanical_data WHERE batch_id = %s", (batch_id,))
    batch['mechanical_data'] = cur.fetchone()
    
    if request.method == 'POST':
        spatial_dims = request.form.get('spatial_dims')
        visual_color = request.form.get('visual_color')
        visual_surface = request.form.get('visual_surface')
        density = request.form.get('density')
        boiling_point = request.form.get('boiling_point')
        melting_point = request.form.get('melting_point')
        batch_good = request.form.get('batch_good')
        batch_good_bool = True if batch_good == 'on' else False
        
        # Вставляем или обновляем данные финального контроля в таблице final_reports
        cur.execute("""
            INSERT INTO final_reports (batch_id, spatial_dims, visual_color, visual_surface, density, boiling_point, melting_point, batch_good)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (batch_id) DO UPDATE SET
                spatial_dims = EXCLUDED.spatial_dims,
                visual_color = EXCLUDED.visual_color,
                visual_surface = EXCLUDED.visual_surface,
                density = EXCLUDED.density,
                boiling_point = EXCLUDED.boiling_point,
                melting_point = EXCLUDED.melting_point,
                batch_good = EXCLUDED.batch_good;
        """, (batch_id, spatial_dims, visual_color, visual_surface, density, boiling_point, melting_point, batch_good_bool))
        
        # Обновляем статус партии
        cur.execute("UPDATE batches SET final_control_done = TRUE WHERE id = %s", (batch_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('report_view', batch_id=batch_id))
    
    cur.close()
    conn.close()
    return render_template('passport.html', batch=batch)

# ------------------------
# Страница с отчётом
# ------------------------
@app.route('/report/<int:batch_id>')
@login_required
def report_view(batch_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM batches WHERE id = %s", (batch_id,))
    batch = cur.fetchone()
    if not batch:
        flash('Партия не найдена', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('choose_batch'))
    
    cur.execute("SELECT * FROM final_reports WHERE batch_id = %s", (batch_id,))
    report = cur.fetchone()
    if not report:
        flash('Отчёт по данной партии отсутствует', 'warning')
        cur.close()
        conn.close()
        return redirect(url_for('choose_batch'))
    
    cur.close()
    conn.close()
    return render_template('report.html', batch=batch, report=report)

# ------------------------
# Скачивание отчёта 
# ------------------------

@app.route('/download_report/<int:batch_id>')
@login_required
def download_report(batch_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Получаем данные о партии
    cur.execute("SELECT * FROM batches WHERE id = %s", (batch_id,))
    batch = cur.fetchone()
    if not batch:
        flash('Партия не найдена', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('choose_batch'))
    
    # Получаем данные финального контроля
    cur.execute("SELECT * FROM final_reports WHERE batch_id = %s", (batch_id,))
    report_data = cur.fetchone()
    if not report_data:
        flash('Отчёт не найден', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('choose_batch'))
    
    cur.close()
    conn.close()
    
    # Подготавливаем данные для отчёта
    control_date = datetime.now().strftime("%d.%m.%Y")  # Или можно взять из report_data, если есть поле
    product = batch['product_name']
    identifier = batch['identifier']
    spatial_dims = report_data.get('spatial_dims', '')
    visual_color = report_data.get('visual_color', '')
    visual_surface = report_data.get('visual_surface', '')
    density = report_data.get('density', '')
    boiling_point = report_data.get('boiling_point', '')
    melting_point = report_data.get('melting_point', '')
    status = "Годна к использованию" if report_data.get('batch_good') else "Не годна к использованию"
    controller = "Иванов И. И."  # Пример, можно брать из сессии или базы
    signature = "____________________"
    notes = ""
    
    # Формируем список строк, где каждая строка – это пара [Параметр, Значение]
    rows = [
        ["Дата проведения контроля", control_date],
        ["Продукт", product],
        ["Идентификатор партии", identifier],
        ["Пространственные замеры", spatial_dims],
        ["Визуальный осмотр — цвет", visual_color],
        ["Визуальный осмотр — поверхность", visual_surface],
        ["Плотность, г/см³", density],
        ["Точка кипения, °C", boiling_point],
        ["Температура плавления, °C", melting_point],
        ["Статус партии", status],
        ["Контролёр", controller],
        ["Подпись", signature],
        ["Примечания", notes]
    ]
    
    # Создаём DataFrame из списка
    df = pd.DataFrame(rows, columns=["Параметр", "Значение"])
    
    # Записываем DataFrame в Excel-файл в памяти и устанавливаем автоширину столбцов
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Отчёт")
        workbook = writer.book
        worksheet = writer.sheets["Отчёт"]
        
        # Автоматическая настройка ширины для каждого столбца
        for col in worksheet.columns:
            max_length = 0
            column = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = max_length + 2  # Немного добавляем пространства
            worksheet.column_dimensions[column].width = adjusted_width
    output.seek(0)
    
    # Формируем имя файла
    filename = f"Отчет по проведению финального контроля партии {product}.xlsx"
    
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ------------------------
# Список отчётов 
# ------------------------
@app.route('/reports')
@login_required
def reports_list():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
      SELECT fr.batch_id, fr.control_date, b.product_name, b.identifier
      FROM final_reports fr
      JOIN batches b ON fr.batch_id = b.id
      ORDER BY fr.control_date DESC
    """)
    reports = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('reports_list.html', reports=reports)


if __name__ == '__main__':
    app.run(debug=True)
