# Migración a Datos Reales - Superstore Dataset

## 📋 Resumen

El sistema ha sido migrado de usar datos auto-generados a usar datos reales del dataset **Sample - Superstore.csv** (archivo estándar de análisis de datos).

---

## ✅ Cambios Realizados

### 1. **Eliminado**
- ❌ `generate_erp_csv.py` - Generador de datos sintéticos
- ❌ `MEJORAS_LOGICA_PRODUCTOS.md` - Documentación de lógica sintética

### 2. **Agregado**
- ✅ `process_superstore_csv.py` - Procesador de datos reales
- ✅ `archive/Sample - Superstore.csv` - Dataset real (9994 registros)

### 3. **Mantenido**
- ✅ `erp_simulator_producer.py` - No requiere cambios (lee de `csv_out/`)
- ✅ `erp_kafka_to_mongo.py` - Compatible con estructura existente
- ✅ Todos los demás componentes del sistema

---

## 🔄 Flujo de Datos

### Antes (Datos Sintéticos):
```
generate_erp_csv.py → csv_out/*.csv → erp_simulator_producer.py → Kafka → MongoDB
```

### Ahora (Datos Reales):
```
archive/Sample - Superstore.csv → process_superstore_csv.py → csv_out/*.csv → erp_simulator_producer.py → Kafka → MongoDB
```

---

## 📊 Estructura del Dataset Real

El archivo `Sample - Superstore.csv` contiene:

### Campos del CSV Original:
- **Row ID**: Identificador de fila
- **Order ID**: ID de orden (se convierte en `sale_id`)
- **Order Date**: Fecha de orden
- **Ship Date**: Fecha de envío
- **Ship Mode**: Modo de envío (Standard Class, Second Class, First Class, Same Day)
- **Customer ID**: ID del cliente
- **Customer Name**: Nombre completo del cliente
- **Segment**: Segmento (Consumer, Corporate, Home Office)
- **Country**: País
- **City**: Ciudad
- **State**: Estado
- **Postal Code**: Código postal
- **Region**: Región (South, West, Central, East)
- **Product ID**: ID del producto
- **Category**: Categoría del producto
- **Sub-Category**: Subcategoría
- **Product Name**: Nombre del producto
- **Sales**: Monto total de venta
- **Quantity**: Cantidad
- **Discount**: Descuento aplicado
- **Profit**: Ganancia

---

## 🔧 Procesamiento de Datos

### `process_superstore_csv.py` realiza:

1. **Extracción de Productos Únicos**
   - Product ID → `product_id` (numérico secuencial)
   - Product Name → `name`
   - Category → `category`
   - Sub-Category → `subcategory`
   - Calcula `unit_price` = Sales / Quantity (revirtiendo descuento)
   - Calcula `unit_cost` = 70% de `unit_price`
   - Genera `supplier_code` basado en categoría
   - Genera `stock` aleatorio (50-500)
   - Usa `Order Date` más antigua como `created_at`

2. **Extracción de Clientes Únicos**
   - Customer ID → `customer_id` (numérico secuencial)
   - Customer Name → `first_name` y `last_name` (split)
   - Genera `email` basado en nombre e ID
   - Genera `phone` aleatorio
   - Segment → `segment`
   - City, State, Country → campos correspondientes
   - Genera `age` aleatorio (25-65)
   - Calcula `registration_date` = primera orden - 30-365 días

3. **Agrupación de Ventas**
   - Order ID → `sale_id` (numérico secuencial)
   - Order Date → `sale_datetime`
   - Customer ID → `customer_id` (mapeado)
   - Ship Mode → `payment_type` (mapeado)
   - Region → `store_id` (STORE-XX)
   - Calcula totales: `gross_amount`, `discount_header`, `tax`, `total_amount`

4. **Items de Venta**
   - Order ID → `sale_id` (mapeado)
   - Genera `line_n` secuencial por orden
   - Product ID → `product_id` (mapeado)
   - Quantity → `quantity`
   - Calcula `unit_price`, `gross_amount`, `line_discount`, `net_amount`

---

## 📈 Estadísticas del Dataset Procesado

Después de ejecutar `process_superstore_csv.py`:

- **Productos**: 1,862 productos únicos
- **Clientes**: 793 clientes únicos
- **Ventas**: 5,009 órdenes
- **Items de Venta**: 9,994 líneas de venta

---

## 🚀 Uso del Sistema

### Paso 1: Procesar el CSV Real

```bash
python process_superstore_csv.py
```

Esto genera los archivos en `csv_out/`:
- `products.csv`
- `customers.csv`
- `sales.csv`
- `sales_items.csv`

### Paso 2: Iniciar Kafka (si no está corriendo)

```bash
docker-compose up -d
```

### Paso 3: Enviar Datos a Kafka

```bash
python erp_simulator_producer.py
```

### Paso 4: Consumir y Guardar en MongoDB

```bash
python erp_kafka_to_mongo.py
```

### Paso 5: Entrenar Modelo de Recomendaciones

```bash
python model_train_reco.py
```

### Paso 6: Iniciar Servicio de Recomendaciones en Tiempo Real

```bash
python reco_service_stream.py
```

### Paso 7: Ver Dashboard de Recomendaciones

```bash
streamlit run print_recommendations_consumer.py
```

---

## 🔍 Mapeo de Campos

### Productos

| CSV Original | Campo ERP | Descripción |
|-------------|-----------|-------------|
| Product ID | `product_id` | ID numérico secuencial |
| Product Name | `name` | Nombre del producto |
| Category | `category` | Categoría |
| Sub-Category | `subcategory` | Subcategoría |
| Sales/Quantity | `unit_price` | Precio unitario calculado |
| - | `unit_cost` | 70% de unit_price |
| - | `supplier_code` | SUP-XXX (basado en categoría) |
| - | `stock` | Aleatorio 50-500 |
| Order Date | `created_at` | Fecha más antigua |
| - | `active` | 1 (activo) |

### Clientes

| CSV Original | Campo ERP | Descripción |
|-------------|-----------|-------------|
| Customer ID | `customer_id` | ID numérico secuencial |
| Customer Name | `first_name` | Primer nombre |
| Customer Name | `last_name` | Apellido |
| - | `email` | Generado (nombre.id@dominio.com) |
| - | `phone` | Generado (+1XXXXXXXXXX) |
| Segment | `segment` | Consumer/Corporate/Home Office |
| City | `city` | Ciudad |
| State | `state` | Estado |
| Country | `country` | País |
| - | `age` | Aleatorio 25-65 |
| Order Date | `registration_date` | Primera orden - 30-365 días |

### Ventas

| CSV Original | Campo ERP | Descripción |
|-------------|-----------|-------------|
| Order ID | `sale_id` | ID numérico secuencial |
| Order Date | `sale_datetime` | Fecha y hora |
| Customer ID | `customer_id` | ID mapeado |
| Ship Mode | `payment_type` | Mapeado (Standard→Efectivo, etc.) |
| Region | `store_id` | STORE-XX |
| - | `items_count` | Cantidad de items en la orden |
| - | `gross_amount` | Total bruto |
| - | `discount_header` | Descuento a nivel cabecera |
| - | `tax` | Impuesto (13%) |
| - | `total_amount` | Total final |

### Items de Venta

| CSV Original | Campo ERP | Descripción |
|-------------|-----------|-------------|
| Order ID | `sale_id` | ID mapeado |
| - | `line_n` | Número de línea secuencial |
| Product ID | `product_id` | ID mapeado |
| Quantity | `quantity` | Cantidad |
| Sales/Quantity | `unit_price` | Precio unitario |
| Sales | `gross_amount` | Monto bruto |
| Discount | `line_discount` | Descuento por línea |
| - | `net_amount` | Monto neto |

---

## 🎯 Ventajas de Usar Datos Reales

✅ **Realismo**: Los datos reflejan comportamientos reales de compra  
✅ **Patrones Reales**: El modelo aprende de relaciones reales entre productos  
✅ **Diversidad**: Mayor variedad en categorías, clientes y productos  
✅ **Calidad**: Datos consistentes y validados  
✅ **Escalabilidad**: Fácil agregar más datos reales en el futuro  

---

## ⚠️ Notas Importantes

1. **Datos Generados**: Algunos campos (email, phone, stock, age, registration_date) se generan automáticamente porque no están en el CSV original.

2. **IDs Numéricos**: Los IDs originales (Product ID, Customer ID, Order ID) se convierten a numéricos secuenciales para mantener compatibilidad con el sistema existente.

3. **Codificación**: El script detecta automáticamente la codificación del archivo (UTF-8, Latin-1, CP1252, etc.).

4. **Descuentos**: Los descuentos se calculan a partir del campo `Discount` del CSV original.

5. **Impuestos**: Se aplica un IVA del 13% sobre la base imponible.

---

## 🔄 Actualizar Datos

Si necesitas actualizar los datos:

1. Reemplaza `archive/Sample - Superstore.csv` con nuevo archivo
2. Ejecuta `python process_superstore_csv.py`
3. Los nuevos CSV se generarán en `csv_out/`
4. Reinicia el flujo de datos (producer → consumer → MongoDB)

---

## 📝 Compatibilidad

✅ **Totalmente compatible** con:
- `erp_simulator_producer.py`
- `erp_kafka_to_mongo.py`
- `model_train_reco.py`
- `reco_service_stream.py`
- `print_recommendations_consumer.py`
- Todos los dashboards y reportes

No se requieren cambios en ningún componente del sistema.



