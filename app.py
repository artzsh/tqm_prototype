from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secretkey'

# ------------------------
# Пример данных пользователей
# ------------------------
users = {
    'employee': 'password123'
}

# ------------------------
# Пример списка партий
# Поле "final_control_done" указывает, прошла ли партия финальный контроль.
# ------------------------
batches = [
    {
        'id': 101,
        'product_name': 'Медная катанка',
        'identifier': 'CU-101',
        'date': '2025-03-01',
        'smelting_data': {
            'temp_regime': '1100-1200°C',
            'time_each_temp': '30 мин при 1100°C, 20 мин при 1200°C',
            'total_time': '50 мин',
            'raw_materials': 'Медная стружка, лом меди',
            'consumed_amount': '500 кг сырья'
        },
        'refining_data': {
            'duration': '15 мин',
            'chemicals': 'Флюсы, раскислители',
            'chemicals_volume': '1 кг раскислителя'
        },
        'cooling_data': {
            'cooling_time': '2 часа',
            'deformation': 'Не обнаружено'
        },
        'heat_treatment_data': {
            'temp_regime': '650°C',
            'duration': '1 час'
        },
        'mechanical_data': {
            'rolled_size': 'Диаметр 8 мм',
            'additional_info': 'Калибровка в 2 этапа'
        },
        'final_control_done': False
    },
    {
        'id': 102,
        'product_name': 'Медный лист',
        'identifier': 'CU-102',
        'date': '2025-03-10',
        'smelting_data': {
            'temp_regime': '1150-1200°C',
            'time_each_temp': '25 мин при 1150°C, 25 мин при 1200°C',
            'total_time': '50 мин',
            'raw_materials': 'Медная катода, лом',
            'consumed_amount': '700 кг сырья'
        },
        'refining_data': {
            'duration': '20 мин',
            'chemicals': 'Десульфурация',
            'chemicals_volume': '1.5 кг реагентов'
        },
        'cooling_data': {
            'cooling_time': '3 часа',
            'deformation': 'Слабое искривление'
        },
        'heat_treatment_data': {
            'temp_regime': '600°C',
            'duration': '2 часа'
        },
        'mechanical_data': {
            'rolled_size': 'Толщина 2 мм',
            'additional_info': 'Правка на вальцах'
        },
        'final_control_done': False
    },
    {
        'id': 103,
        'product_name': 'Медная проволока',
        'identifier': 'CU-103',
        'date': '2025-03-15',
        'smelting_data': {
            'temp_regime': '1050-1100°C',
            'time_each_temp': '20 мин при 1050°C, 30 мин при 1100°C',
            'total_time': '50 мин',
            'raw_materials': 'Лом меди, чистая катода',
            'consumed_amount': '300 кг сырья'
        },
        'refining_data': {
            'duration': '10 мин',
            'chemicals': 'Флюсы',
            'chemicals_volume': '0.8 кг'
        },
        'cooling_data': {
            'cooling_time': '1.5 часа',
            'deformation': 'Не обнаружено'
        },
        'heat_treatment_data': {
            'temp_regime': '700°C',
            'duration': '30 мин'
        },
        'mechanical_data': {
            'rolled_size': 'Диаметр 1 мм',
            'additional_info': 'Протяжка на станах'
        },
        'final_control_done': False  # Допустим, уже прошла финальный контроль
    },
]

# ------------------------
# Храним результаты финального контроля в памяти
# ------------------------
final_reports = {}

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
# 1) Ввод даты
# 2) Выпадающий список с партиями, у которых final_control_done=False и дата >= введённой
# 3) Кнопка "Далее" -> переходим на паспорт изделия
# ------------------------
@app.route('/choose_batch', methods=['GET', 'POST'])
@login_required
def choose_batch():
    if request.method == 'POST':
        input_date = request.form.get('batch_date')
        selected_batch_id = request.form.get('batch_id')
        
        if not input_date:
            flash('Введите дату', 'warning')
            return redirect(url_for('choose_batch'))
        
        if not selected_batch_id:
            flash('Выберите партию', 'warning')
            return redirect(url_for('choose_batch'))
        
        # Переходим к паспорту изделия
        return redirect(url_for('passport_view', batch_id=selected_batch_id))
    
    # При GET-запросе показываем форму
    return render_template('choose_batch.html', batches=batches)

# ------------------------
# Страница паспорта изделия
# Показываем данные о плавке, рафинировании и т.д.
# Форма для финального контроля:
#   - Пространственные замеры (*x*x*)
#   - Визуальный осмотр (пара текстовых полей)
#   - Физические качества (плотность, т. кипения, т. плавления)
#   - Чекбокс "Партия годна"
# ------------------------
@app.route('/passport/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def passport_view(batch_id):
    # Ищем партию
    batch = next((b for b in batches if b['id'] == batch_id), None)
    if not batch:
        flash('Партия не найдена', 'danger')
        return redirect(url_for('choose_batch'))
    
    if request.method == 'POST':
        # Считываем данные из формы
        spatial_dims = request.form.get('spatial_dims')  # *x*x* (пример: 10x20x30)
        visual_color = request.form.get('visual_color')
        visual_surface = request.form.get('visual_surface')
        
        density = request.form.get('density')
        boiling_point = request.form.get('boiling_point')
        melting_point = request.form.get('melting_point')
        
        batch_good = request.form.get('batch_good')  # on/None
        
        # Сохраняем в final_reports
        final_reports[batch_id] = {
            'batch_id': batch_id,
            'spatial_dims': spatial_dims,
            'visual_color': visual_color,
            'visual_surface': visual_surface,
            'density': density,
            'boiling_point': boiling_point,
            'melting_point': melting_point,
            'batch_good': (batch_good == 'on')
        }
        
        # Помечаем в batch, что финальный контроль пройден
        batch['final_control_done'] = True
        
        # Переходим на страницу с отчётом
        return redirect(url_for('report_view', batch_id=batch_id))
    
    # При GET-запросе показываем паспорт
    return render_template('passport.html', batch=batch)

# ------------------------
# Страница с отчётом
# Отображаем данные финального контроля, название партии и ссылку на скачивание отчёта
# ------------------------
@app.route('/report/<int:batch_id>')
@login_required
def report_view(batch_id):
    batch = next((b for b in batches if b['id'] == batch_id), None)
    if not batch:
        flash('Партия не найдена', 'danger')
        return redirect(url_for('choose_batch'))
    
    report = final_reports.get(batch_id)
    if not report:
        flash('Отчёт по данной партии отсутствует', 'warning')
        return redirect(url_for('choose_batch'))
    
    return render_template('report.html', batch=batch, report=report)

# ------------------------
# Маршрут для скачивания PDF (заглушка)
# ------------------------
@app.route('/download_report/<int:batch_id>')
@login_required
def download_report(batch_id):
    # В реальном приложении здесь можно сгенерировать PDF
    # и отдать пользователю файл. Ниже — упрощённый пример выдачи текстового файла.
    report_data = final_reports.get(batch_id)
    if not report_data:
        flash('Отчёт не найден', 'danger')
        return redirect(url_for('choose_batch'))
    
    # Формируем упрощённый текст
    output_text = (
        f"Отчёт по партии {batch_id}\n\n"
        f"Пространственные замеры: {report_data['spatial_dims']}\n"
        f"Визуальный осмотр (цвет): {report_data['visual_color']}\n"
        f"Визуальный осмотр (поверхность): {report_data['visual_surface']}\n"
        f"Плотность: {report_data['density']} г/см3\n"
        f"Точка кипения: {report_data['boiling_point']} °C\n"
        f"Температура плавления: {report_data['melting_point']} °C\n"
        f"Партия годна: {'Да' if report_data['batch_good'] else 'Нет'}\n"
    )
    
    # Отдаём текстовый файл в качестве примера
    return send_file(
        io.BytesIO(output_text.encode('utf-8')),
        as_attachment=True,
        download_name=f"report_{batch_id}.txt",
        mimetype='text/plain'
    )

if __name__ == '__main__':
    app.run(debug=True)
