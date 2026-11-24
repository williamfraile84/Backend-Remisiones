import sqlite3

db_path = r"c:\Users\yovan\Music\Nueva carpeta\SISTEMA_FRUVER\sistema_fruver\backend\storage_data\app.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Clientes
clientes = [
    (1, 1, "HOTEL TEQUENDAMA SUITES & CONVENCIONES", "900.123.456-1", "Carrera 10 # 26-21, Centro Internacional, Bogotá", "601 382 0300", "compras@tequendamasuites.com", 105, 1),
    (2, 1, "RESTAURANTE EL PORTAL DEL BOSQUE S.A.S.", "901.789.012-3", "Calle 85 # 12-44, Zona Rosa, Bogotá", "315 777 9876", "pedidos@elportaldelbosque.co", 88, 1),
    (3, 1, "SUPERMERCADO MERCAFÁCIL LA 38", "830.456.789-8", "Avenida Calle 38 Sur # 14-20, Bogotá", "320 888 4321", "mercafacil.ventas@gmail.com", 13, 1)
]

for c in clientes:
    cursor.execute("""
        INSERT INTO clientes (id, empresa_id, razon_social, nit, direccion, telefono, email, consecutivo_remision_actual, activo, creado_en, actualizado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            razon_social=excluded.razon_social,
            nit=excluded.nit,
            direccion=excluded.direccion,
            telefono=excluded.telefono,
            email=excluded.email,
            consecutivo_remision_actual=excluded.consecutivo_remision_actual
    """, c)

# 2. Pedido 1
cursor.execute("SELECT id FROM pedidos WHERE numero_remision='REM-104'")
if not cursor.fetchone():
    cursor.execute("""
        INSERT INTO pedidos (
            id, empresa_id, usuario_id, cliente_id, numero_oc, numero_remision,
            fecha_emision, fecha_entrega, numero_canastas, observaciones,
            utilidad_global, factura_cargada, remision_firmada_cargada, completado, activo,
            creado_en, actualizado_en
        ) VALUES (
            1, 1, 1, 1, 'OC-2026-981', 'REM-104',
            '2026-11-23', '2026-11-24', '12',
            'Recibido a satisfacción por el responsable designado en el muelle de descarga 3.',
            30.0, 0, 0, 0, 1, datetime('now'), datetime('now')
        )
    """)

    # Items del pedido 1
    items = [
        (1, 1, 2, 40.0, 1, 1, 6500.0, 9300.0, 40.0, 30.0, 6500.0, 0.0, 0, 0, "AGUACATE HASS", "Calidad extra, maduración media", 1, 1),
        (2, 1, 1, 25.0, 1, 1, 4200.0, 6000.0, 25.0, 30.0, 4200.0, 0.0, 0, 0, "ARVEJA DESGRANADA", "Seleccionada y empacada en bolsa microperforada", 1, 2),
        (3, 1, 4, 30.0, 1, 1, 3100.0, 4400.0, 30.0, 29.5, 3100.0, 0.0, 0, 0, "ARVEJA CASCARA", "Fresco de plaza de mercado", 1, 3),
        (4, 1, 5, 50.0, 1, 1, 1800.0, 2600.0, 50.0, 30.8, 1800.0, 0.0, 0, 0, "AUYAMA", "Porciones enteras en canastilla", 1, 4),
    ]
    for it in items:
        cursor.execute("""
            INSERT INTO pedido_items (
                id, pedido_id, producto_id, cantidad, unidad_medida_id, tipo_empaque_id,
                precio_costo_unitario, precio_venta_unitario, peso_neto, porcentaje_utilidad,
                costo_real_kilo, gasto_asignado_kilo, precio_venta_manual, surtido,
                producto_nombre, notas, activo, orden, creado_en, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, it)

    # Gasto pedido 1
    cursor.execute("""
        INSERT INTO pedido_gastos (
            id, pedido_id, concepto_gasto_id, descripcion, monto, distribuir_en_costo, activo, creado_en, actualizado_en
        ) VALUES (
            1, 1, 1, 'FLETE TERRESTRE BODEGA CENTRAL', 45000.0, 1, 1, datetime('now'), datetime('now')
        )
    """)

# Pedido 2 (Historial)
cursor.execute("SELECT id FROM pedidos WHERE numero_remision='REM-103'")
if not cursor.fetchone():
    cursor.execute("""
        INSERT INTO pedidos (
            id, empresa_id, usuario_id, cliente_id, numero_oc, numero_remision,
            fecha_emision, fecha_entrega, numero_canastas, observaciones,
            utilidad_global, factura_cargada, remision_firmada_cargada, completado, activo,
            creado_en, actualizado_en
        ) VALUES (
            2, 1, 1, 1, 'OC-2026-950', 'REM-103',
            '2026-11-20', '2026-11-21', '10',
            'Despachado y recibido a satisfacción. Factura FV-4012 emitida.',
            30.0, 1, 1, 1, 1, datetime('now', '-3 days'), datetime('now', '-2 days')
        )
    """)

conn.commit()
conn.close()
print("Datos de demostración sembrados con éxito.")
