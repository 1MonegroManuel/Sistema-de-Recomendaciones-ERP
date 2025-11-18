# process_superstore_csv.py
# Procesa el CSV real de Superstore y genera las estructuras para el ERP
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import random
import re

# Configuración
INPUT_CSV = Path("./archive/Sample - Superstore.csv")
OUTPUT_DIR = Path("./csv_out")
OUTPUT_DIR.mkdir(exist_ok=True)

# Para generar datos faltantes
random.seed(42)

def parse_date(date_str):
    """Convierte fecha del formato MM/DD/YYYY a YYYY-MM-DD"""
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return date_str

def parse_datetime(date_str):
    """Convierte fecha a datetime para ordenamiento"""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y")
    except:
        return datetime.now()

def split_name(full_name):
    """Separa nombre completo en first_name y last_name"""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = " ".join(parts[1:])
    else:
        first_name = parts[0] if parts else "Unknown"
        last_name = ""
    return first_name, last_name

def generate_email(first_name, last_name, customer_id):
    """Genera email basado en nombre e ID"""
    base = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}"
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
    return f"{base}{customer_id[-2:]}@{random.choice(domains)}"

def generate_phone(customer_id):
    """Genera teléfono basado en ID"""
    # Simular formato de teléfono
    return f"+1{random.randint(2000000000, 9999999999)}"

def generate_registration_date(order_date):
    """Genera fecha de registro antes de la primera compra"""
    try:
        dt = datetime.strptime(order_date, "%m/%d/%Y")
        # Restar entre 30 y 365 días
        days_before = random.randint(30, 365)
        reg_date = dt - timedelta(days=days_before)
        return reg_date.strftime("%Y-%m-%d")
    except:
        return "2020-01-01"

def calculate_unit_price(sales, quantity, discount):
    """Calcula precio unitario antes de descuento"""
    if quantity == 0:
        return 0.0
    # Sales ya incluye descuento, necesitamos el precio original
    discounted_amount = float(sales)
    if discount > 0:
        # Revertir descuento: discounted = original * (1 - discount)
        original = discounted_amount / (1 - discount)
    else:
        original = discounted_amount
    return round(original / quantity, 2)

def map_ship_mode_to_payment(ship_mode):
    """Mapea Ship Mode a Payment Type"""
    mapping = {
        "Standard Class": "Efectivo",
        "Second Class": "Tarjeta",
        "First Class": "Tarjeta",
        "Same Day": "QR"
    }
    return mapping.get(ship_mode, "Transferencia")

def main():
    print("Procesando CSV de Superstore...")
    
    # Estructuras para almacenar datos únicos
    products_dict = {}  # product_id -> product data
    customers_dict = {}  # customer_id -> customer data
    sales_dict = {}  # order_id -> sale header
    sales_items_list = []  # lista de items
    
    # Para rastrear fechas de clientes
    customer_first_order = {}  # customer_id -> primera fecha de orden
    
    # Leer CSV (intentar diferentes codificaciones)
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    reader = None
    for encoding in encodings:
        try:
            f = open(INPUT_CSV, 'r', encoding=encoding)
            reader = csv.DictReader(f)
            # Probar leer una línea
            next(reader)
            f.seek(0)  # Volver al inicio
            reader = csv.DictReader(f)
            print(f"Codificacion detectada: {encoding}")
            break
        except (UnicodeDecodeError, UnicodeError):
            if 'f' in locals():
                f.close()
            continue
    
    if reader is None:
        raise ValueError(f"No se pudo leer el archivo con ninguna codificacion: {encodings}")
    
    f = open(INPUT_CSV, 'r', encoding=encoding)
    reader = csv.DictReader(f)
    
    line_n_by_order = defaultdict(int)  # Para line_n por Order ID
    
    try:
        for row in reader:
            # Procesar Producto
            product_id = row['Product ID'].strip()
            if product_id not in products_dict:
                product_name = row['Product Name'].strip()
                category = row['Category'].strip()
                subcategory = row['Sub-Category'].strip()
                
                # Calcular precio unitario promedio (usaremos el de esta fila)
                sales = float(row['Sales'])
                quantity = int(float(row['Quantity']))
                discount = float(row['Discount'])
                unit_price = calculate_unit_price(sales, quantity, discount)
                
                # Calcular costo (aproximado: 70% del precio)
                unit_cost = round(unit_price * 0.7, 2)
                
                # Generar supplier_code
                supplier_code = f"SUP-{category[:3].upper()}"
                
                # Stock estimado (aleatorio entre 50-500)
                stock = random.randint(50, 500)
                
                # Fecha de creación (usar Order Date más antigua)
                created_at = parse_date(row['Order Date'])
                
                products_dict[product_id] = {
                    'product_id': product_id,
                    'name': product_name,
                    'category': category,
                    'subcategory': subcategory,
                    'unit_price': unit_price,
                    'unit_cost': unit_cost,
                    'supplier_code': supplier_code,
                    'stock': stock,
                    'created_at': created_at,
                    'active': 1
                }
            
            # Procesar Cliente
            customer_id = row['Customer ID'].strip()
            if customer_id not in customers_dict:
                full_name = row['Customer Name'].strip()
                first_name, last_name = split_name(full_name)
                email = generate_email(first_name, last_name, customer_id)
                phone = generate_phone(customer_id)
                segment = row['Segment'].strip()
                city = row['City'].strip()
                state = row['State'].strip()
                country = row['Country'].strip()
                
                # Guardar fecha de primera orden para calcular registration_date después
                order_date = row['Order Date']
                customer_first_order[customer_id] = order_date
                
                customers_dict[customer_id] = {
                    'customer_id': customer_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                    'city': city,
                    'state': state,
                    'country': country,
                    'segment': segment,
                    'age': random.randint(25, 65),  # Edad estimada
                    'registration_date': None  # Se calculará después
                }
            else:
                # Actualizar fecha de primera orden si es más antigua
                order_date = row['Order Date']
                if order_date < customer_first_order.get(customer_id, '9999/99/99'):
                    customer_first_order[customer_id] = order_date
            
            # Procesar Venta (cabecera) - agrupar por Order ID
            order_id = row['Order ID'].strip()
            if order_id not in sales_dict:
                order_date = row['Order Date']
                ship_mode = row['Ship Mode']
                payment_type = map_ship_mode_to_payment(ship_mode)
                
                # Calcular totales (se actualizarán después)
                sales_dict[order_id] = {
                    'sale_id': order_id,
                    'sale_datetime': f"{parse_date(order_date)} {random.randint(8, 20):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}",
                    'customer_id': customer_id,
                    'store_id': f"STORE-{row['Region'][:2].upper()}",  # Usar región como store
                    'payment_type': payment_type,
                    'items_count': 0,  # Se actualizará
                    'gross_amount': 0.0,
                    'discount_header': 0.0,
                    'tax': 0.0,
                    'total_amount': 0.0
                }
            
            # Procesar Item de Venta
            line_n_by_order[order_id] += 1
            sales = float(row['Sales'])
            quantity = int(float(row['Quantity']))
            discount = float(row['Discount'])
            unit_price = calculate_unit_price(sales, quantity, discount)
            gross_amount = round(unit_price * quantity, 2)
            line_discount = round(gross_amount * discount, 2)
            net_amount = round(gross_amount - line_discount, 2)
            
            sales_items_list.append({
                'sale_id': order_id,
                'line_n': line_n_by_order[order_id],
                'product_id': product_id,
                'quantity': quantity,
                'unit_price': unit_price,
                'gross_amount': gross_amount,
                'line_discount': line_discount,
                'net_amount': net_amount
            })
    finally:
        f.close()
    
    # Calcular registration_date para clientes
    for customer_id, customer in customers_dict.items():
        first_order_date = customer_first_order.get(customer_id)
        if first_order_date:
            customer['registration_date'] = generate_registration_date(first_order_date)
        else:
            customer['registration_date'] = "2020-01-01"
    
    # Calcular totales de ventas
    sales_items_by_order = defaultdict(list)
    for item in sales_items_list:
        sales_items_by_order[item['sale_id']].append(item)
    
    for order_id, items in sales_items_by_order.items():
        sale = sales_dict[order_id]
        sale['items_count'] = len(items)
        gross_total = sum(item['gross_amount'] for item in items)
        discount_total = sum(item['line_discount'] for item in items)
        net_total = sum(item['net_amount'] for item in items)
        
        # Descuento a nivel cabecera (pequeño, 0-2%)
        header_discount_pct = random.uniform(0, 0.02)
        header_discount = round(net_total * header_discount_pct, 2)
        taxable_base = net_total - header_discount
        tax_rate = 0.13  # 13% IVA
        tax = round(taxable_base * tax_rate, 2)
        total_amount = round(taxable_base + tax, 2)
        
        sale['gross_amount'] = round(gross_total, 2)
        sale['discount_header'] = round(header_discount, 2)
        sale['tax'] = tax
        sale['total_amount'] = total_amount
    
    # Convertir productos a lista y asignar IDs numéricos
    products_list = []
    product_id_map = {}  # product_id original -> product_id numérico
    for idx, (original_id, product) in enumerate(products_dict.items(), 1):
        product_id_map[original_id] = idx
        product['product_id'] = idx
        products_list.append(product)
    
    # Actualizar sales_items con product_id numérico
    for item in sales_items_list:
        original_pid = item['product_id']
        item['product_id'] = product_id_map[original_pid]
    
    # Convertir clientes a lista y asignar IDs numéricos
    customers_list = []
    customer_id_map = {}  # customer_id original -> customer_id numérico
    for idx, (original_id, customer) in enumerate(customers_dict.items(), 1):
        customer_id_map[original_id] = idx
        customer['customer_id'] = idx
        customers_list.append(customer)
    
    # Actualizar sales y sales_items con customer_id numérico
    sales_list = []
    sale_id_map = {}  # order_id original -> sale_id numérico
    for idx, (original_id, sale) in enumerate(sales_dict.items(), 1):
        sale_id_map[original_id] = idx
        sale['sale_id'] = idx
        sale['customer_id'] = customer_id_map[sale['customer_id']]
        sales_list.append(sale)
    
    # Actualizar sales_items con sale_id numérico
    for item in sales_items_list:
        original_sid = item['sale_id']
        item['sale_id'] = sale_id_map[original_sid]
    
    # Escribir CSVs
    print(f"Productos: {len(products_list)}")
    with open(OUTPUT_DIR / "products.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'product_id', 'name', 'category', 'subcategory', 'unit_price', 
            'unit_cost', 'supplier_code', 'stock', 'created_at', 'active'
        ])
        writer.writeheader()
        writer.writerows(products_list)
    
    print(f"Clientes: {len(customers_list)}")
    with open(OUTPUT_DIR / "customers.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'customer_id', 'first_name', 'last_name', 'email', 'phone',
            'city', 'state', 'country', 'segment', 'age', 'registration_date'
        ])
        writer.writeheader()
        writer.writerows(customers_list)
    
    print(f"Ventas: {len(sales_list)}")
    with open(OUTPUT_DIR / "sales.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sale_id', 'sale_datetime', 'customer_id', 'store_id', 'payment_type',
            'items_count', 'gross_amount', 'discount_header', 'tax', 'total_amount'
        ])
        writer.writeheader()
        writer.writerows(sales_list)
    
    print(f"Items de Venta: {len(sales_items_list)}")
    with open(OUTPUT_DIR / "sales_items.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sale_id', 'line_n', 'product_id', 'quantity', 'unit_price',
            'gross_amount', 'line_discount', 'net_amount'
        ])
        writer.writeheader()
        writer.writerows(sales_items_list)
    
    print(f"Procesamiento completado. Archivos en: {OUTPUT_DIR.resolve()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

