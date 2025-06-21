from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, g, make_response
import sqlite3
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage
import pdfkit
import io
import xlsxwriter
import platform  # <--- Agrega esta línea

# Detectar sistema operativo y configurar pdfkit según OS
if platform.system() == 'Windows':
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
else:
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# ... aquí sigue todo tu código ...
ADMIN_USERS = {
    'michael': 'michael2025@',
    'samuel': 'michael2025@'
}

DATABASE = 'barberia_michael.db'

# Configuración pdfkit (ajusta ruta wkhtmltopdf según tu sistema)
PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
# En Windows algo como:
# PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT NOT NULL,
            servicio TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            mensaje_admin TEXT,
            barbero TEXT NOT NULL DEFAULT 'michael'
        )
    ''')
    conn.commit()
    conn.close()

def agregar_columna_barbero_si_no_existe():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE citas ADD COLUMN barbero TEXT NOT NULL DEFAULT 'michael';")
        print("Columna 'barbero' añadida correctamente.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("La columna 'barbero' ya existe.")
        else:
            print("Error al añadir columna 'barbero':", e)
    conn.commit()
    conn.close()

def rellenar_barbero_citas_viejas():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE citas SET barbero = 'michael' WHERE barbero IS NULL OR barbero = ''")
    conn.commit()
    conn.close()
    print("Citas viejas actualizadas con barbero por defecto.")

horarios = {
    'domingo':   ('09:00', '16:00'),
    'lunes':     ('09:00', '18:30'),
    'martes':    ('09:00', '17:00'),
    'miércoles': ('09:00', '18:30'),
    'jueves':    ('09:00', '17:00'),
    'viernes':   ('09:00', '19:00'),
    'sábado':    ('09:00', '14:00')
}

def generar_horas_disponibles(dia_semana, fecha, db, barbero):
    if dia_semana not in horarios:
        return []

    inicio, fin = horarios[dia_semana]
    inicio_dt = datetime.strptime(inicio, '%H:%M')
    fin_dt = datetime.strptime(fin, '%H:%M')

    c = db.cursor()
    c.execute("SELECT hora FROM citas WHERE fecha = ? AND barbero = ?", (fecha, barbero))
    ocupadas = [row[0] for row in c.fetchall()]

    horas_disponibles = []
    actual = inicio_dt
    while actual <= fin_dt:
        hora_str = actual.strftime('%H:%M')
        if hora_str not in ocupadas:
            horas_disponibles.append(hora_str)
        actual += timedelta(minutes=30)

    return horas_disponibles

def enviar_correo(destinatario_cliente, nombre, servicio, fecha, hora, estado='confirmada', mensaje_admin='', barbero=''):
    remitente = 'jesusaaj7@gmail.com'
    clave = 'qsuz djja lwod stdc'
    
    # Define el correo destino para notificación interna dependiendo del barbero
    if barbero == 'michael':
        correo_interno = 'jesusaaj7@gmail.com'
    elif barbero == 'samuel':
        correo_interno = 'gejesu34@gmail.com'
    else:
        correo_interno = 'jesusaaj7@gmail.com'  # Por defecto

    asunto = f'Cita {estado} - Barbería Michael'

    cuerpo_texto = f"""
Hola {nombre},

Tu cita ha sido {estado} en la Barbería Michael con el barbero {barbero}.

Fecha: {fecha}
Hora: {hora}
Servicio: {servicio}

{mensaje_admin}

¡Gracias por preferirnos!
"""

    cuerpo_html = f"""
<html>
<body style="font-family: Arial; padding: 20px;">
    <h2>💈 Barbería Michael</h2>
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Tu cita ha sido <strong>{estado}</strong> con el barbero <strong>{barbero}</strong>. Detalles:</p>
    <ul>
        <li><strong>Fecha:</strong> {fecha}</li>
        <li><strong>Hora:</strong> {hora}</li>
        <li><strong>Servicio:</strong> {servicio}</li>
    </ul>
    <p><strong>Mensaje del administrador:</strong> {mensaje_admin}</p>
    <p>¡Gracias por preferirnos!</p>
</body>
</html>
"""

    msg = EmailMessage()
    msg['Subject'] = asunto
    msg['From'] = remitente
    msg['To'] = destinatario_cliente
    msg['Cc'] = correo_interno  # Copia a quien corresponde según barbero
    msg.set_content(cuerpo_texto)
    msg.add_alternative(cuerpo_html, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, clave)
            smtp.send_message(msg)
    except Exception as e:
        print("Error al enviar correo:", e)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in ADMIN_USERS and ADMIN_USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            flash(f'Has iniciado sesión como {username}.', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

@app.route('/agendar', methods=['GET','POST'])
def agendar():
    if request.method == 'POST':
        campos = ['nombre', 'email', 'telefono', 'servicio', 'fecha', 'hora', 'barbero']
        for campo in campos:
            if not request.form.get(campo):
                flash(f'El campo {campo} es obligatorio.', 'danger')
                return redirect(url_for('agendar'))

        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        servicio = request.form['servicio']
        fecha = request.form['fecha']
        hora = request.form['hora']
        barbero = request.form['barbero']

        dia_semana_eng = datetime.strptime(fecha, '%Y-%m-%d').strftime('%A').lower()
        dias_map = {
            'monday': 'lunes',
            'tuesday': 'martes',
            'wednesday': 'miércoles',
            'thursday': 'jueves',
            'friday': 'viernes',
            'saturday': 'sábado',
            'sunday': 'domingo'
        }
        dia_es = dias_map.get(dia_semana_eng, '')

        db = get_db()
        horas_disp = generar_horas_disponibles(dia_es, fecha, db, barbero)
        if hora not in horas_disp:
            flash('La hora seleccionada ya está ocupada, por favor elige otra.', 'danger')
            return redirect(url_for('agendar'))

        c = db.cursor()
        c.execute("""
            INSERT INTO citas (nombre, email, telefono, servicio, fecha, hora, barbero)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nombre, email, telefono, servicio, fecha, hora, barbero))
        db.commit()

        enviar_correo(email, nombre, servicio, fecha, hora, 'confirmada', '', barbero)

        flash('✅ Cita agendada con éxito. Revisa tu correo.', 'success')
        return redirect(url_for('index'))

    barberos = list(ADMIN_USERS.keys())
    return render_template('agendar.html', barberos=barberos)

@app.route('/horas_disponibles', methods=['POST'])
def horas_disponibles():
    data = request.get_json()
    fecha = data.get('fecha')
    barbero = data.get('barbero')

    if not fecha or not barbero:
        return jsonify([])

    dia_semana_eng = datetime.strptime(fecha, '%Y-%m-%d').strftime('%A').lower()
    dias_map = {
        'monday': 'lunes',
        'tuesday': 'martes',
        'wednesday': 'miércoles',
        'thursday': 'jueves',
        'friday': 'viernes',
        'saturday': 'sábado',
        'sunday': 'domingo'
    }
    dia_semana = dias_map.get(dia_semana_eng, '')
    db = get_db()
    disponibles = generar_horas_disponibles(dia_semana, fecha, db, barbero)
    return jsonify(disponibles)

@app.route('/admin', methods=['GET','POST'])
def admin():
    if not session.get('logged_in'):
        flash('Debes iniciar sesión para acceder a la intranet.', 'warning')
        return redirect(url_for('login'))

    db = get_db()
    c = db.cursor()
    barbero_actual = session.get('username')

    if request.method == 'POST':
        cita_id = request.form['id']
        accion = request.form['accion']
        mensaje_admin = request.form.get('mensaje', '')

        c.execute("SELECT nombre, email, servicio, fecha, hora, barbero FROM citas WHERE id = ?", (cita_id,))
        cita = c.fetchone()

        if cita:
            nombre, email, servicio, fecha, hora, barbero = cita
            nuevo_estado = 'aceptada' if accion == 'aceptar' else 'rechazada'

            c.execute("UPDATE citas SET estado = ?, mensaje_admin = ? WHERE id = ?", (nuevo_estado, mensaje_admin, cita_id))
            db.commit()
            enviar_correo(email, nombre, servicio, fecha, hora, nuevo_estado, mensaje_admin, barbero)

        return redirect(url_for('admin'))

    c.execute("SELECT * FROM citas WHERE estado = 'pendiente' AND barbero = ?", (barbero_actual,))
    pendientes = c.fetchall()
    return render_template('admin.html', citas=pendientes, barbero=barbero_actual)

@app.route('/admin/reporte_pdf')
def reporte_pdf():
    if not session.get('logged_in'):
        flash('Debes iniciar sesión para acceder.', 'warning')
        return redirect(url_for('login'))

    barbero_actual = session.get('username')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT nombre, email, telefono, servicio, fecha, hora, estado FROM citas WHERE barbero = ?", (barbero_actual,))
    citas = c.fetchall()

    rendered = render_template('reporte_pdf.html', citas=citas, barbero=barbero_actual)
    pdf = pdfkit.from_string(rendered, False, configuration=PDFKIT_CONFIG)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_citas_{barbero_actual}.pdf'
    return response


@app.route('/admin/reporte_excel')
def reporte_excel():
    if not session.get('logged_in'):
        flash('Debes iniciar sesión para acceder.', 'warning')
        return redirect(url_for('login'))

    barbero_actual = session.get('username')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT nombre, email, telefono, servicio, fecha, hora, estado FROM citas WHERE barbero = ?", (barbero_actual,))
    citas = c.fetchall()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    headers = ['Nombre', 'Email', 'Teléfono', 'Servicio', 'Fecha', 'Hora', 'Estado']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, cita in enumerate(citas, 1):
        for col_num, value in enumerate(cita):
            worksheet.write(row_num, col_num, value)

    workbook.close()
    output.seek(0)

    response = make_response(output.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_citas_{barbero_actual}.xlsx'
    return response
@app.route('/registros', methods=['GET'])
def registros():
    if not session.get('logged_in'):
        flash('Debes iniciar sesión para acceder a la intranet.', 'warning')
        return redirect(url_for('login'))

    db = get_db()
    barbero_actual = session.get('username')
    fecha_seleccionada = request.args.get('fecha')

    # Si no hay fecha seleccionada, mostrar la fecha de hoy
    if not fecha_seleccionada:
        fecha_seleccionada = datetime.now().strftime('%Y-%m-%d')

    c = db.cursor()
    # Consultar citas para ese barbero y fecha, sin importar el estado
    c.execute("""
        SELECT * FROM citas
        WHERE barbero = ? AND fecha = ?
        ORDER BY hora ASC
    """, (barbero_actual, fecha_seleccionada))
    registros = c.fetchall()

    return render_template('registros.html', registros=registros, fecha=fecha_seleccionada, barbero=barbero_actual)

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    else:
        agregar_columna_barbero_si_no_existe()
        rellenar_barbero_citas_viejas()

    app.run(debug=True, host='0.0.0.0', port=10000)
