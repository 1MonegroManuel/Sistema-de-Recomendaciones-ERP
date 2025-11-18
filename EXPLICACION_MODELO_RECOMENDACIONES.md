# 🤖 Explicación del Modelo de Recomendaciones

## 📚 Índice
1. [Concepto General](#concepto-general)
2. [Fase 1: Entrenamiento (`model_train_reco.py`)](#fase-1-entrenamiento)
3. [Fase 2: Generación de Recomendaciones (`reco_service_stream.py`)](#fase-2-generación-de-recomendaciones)
4. [Ejemplo Práctico](#ejemplo-práctico)

---

## 🎯 Concepto General

El modelo utiliza **Item-Based Collaborative Filtering** (filtrado colaborativo basado en items) con **similitud coseno**. La idea principal es:

> **"Si dos productos se compran juntos frecuentemente, entonces son similares"**

### Flujo del Sistema:
```
1. ENTRENAMIENTO (model_train_reco.py)
   └─> Analiza TODO el histórico de ventas
   └─> Calcula qué productos se compran juntos
   └─> Guarda matriz de similitudes → models/item_sim.pkl

2. RECOMENDACIONES EN TIEMPO REAL (reco_service_stream.py)
   └─> Recibe una nueva venta
   └─> Obtiene los productos en el carrito
   └─> Busca productos similares en el modelo entrenado
   └─> Recomienda los top-N productos más similares
```

---

## 📊 Fase 1: Entrenamiento (`model_train_reco.py`)

### Paso 1: Cargar Datos Históricos
```python
# Lee TODAS las ventas desde MongoDB
sales_items = [
    {sale_id: 1, product_id: 101},  # Venta 1: producto 101
    {sale_id: 1, product_id: 205},  # Venta 1: producto 205
    {sale_id: 2, product_id: 101},  # Venta 2: producto 101
    {sale_id: 2, product_id: 305},  # Venta 2: producto 305
    ...
]

# Agrupa por venta (crea "cestas de compra")
baskets = {
    1: [101, 205],      # En la venta 1 se compraron productos 101 y 205
    2: [101, 305],      # En la venta 2 se compraron productos 101 y 305
    3: [205, 305, 401], # En la venta 3 se compraron productos 205, 305 y 401
    ...
}
```

### Paso 2: Calcular Co-ocurrencias (Productos que aparecen juntos)

Para cada venta, cuenta cuántas veces dos productos aparecen juntos:

```python
# Ejemplo con ventas:
Venta 1: [101, 205]     → Productos 101 y 205 aparecen juntos
Venta 2: [101, 305]     → Productos 101 y 305 aparecen juntos
Venta 3: [205, 305, 401] → Pares: (205,305), (205,401), (305,401)

# Resultado: pair_count
pair_count = {
    101: {
        205: 1,  # Productos 101 y 205 aparecen juntos 1 vez
        305: 1,  # Productos 101 y 305 aparecen juntos 1 vez
    },
    205: {
        101: 1,  # Productos 205 y 101 aparecen juntos 1 vez
        305: 1,  # Productos 205 y 305 aparecen juntos 1 vez
        401: 1,  # Productos 205 y 401 aparecen juntos 1 vez
    },
    ...
}
```

**Peso por Recencia**: Las ventas recientes tienen más peso que las antiguas
```python
# Si una venta es de hace 3 meses, tiene peso 0.5
# Si una venta es de hace 6 meses, tiene peso 0.25
# Si una venta es reciente, tiene peso 1.0
w = time_decay_weight(fecha_venta, fecha_referencia)
```

### Paso 3: Calcular Similitud Coseno

La similitud coseno mide qué tan similares son dos productos basándose en:
- **Cuántas veces se compran juntos** (co-ocurrencia)
- **Cuántas veces se compran individualmente** (frecuencia)

**Fórmula**:
```
similitud(A, B) = co_ocurrencias(A, B) / (√frecuencia(A) × √frecuencia(B))
```

**Ejemplo**:
```python
# Producto 101 se compró 10 veces en total
# Producto 205 se compró 8 veces en total
# Productos 101 y 205 aparecen juntos 3 veces

similitud(101, 205) = 3 / (√10 × √8)
                    = 3 / (3.16 × 2.83)
                    = 3 / 8.94
                    = 0.336
```

**Código**:
```python
for producto_i, vecinos in pair_count.items():
    for producto_j, co_ocurrencias_ij in vecinos.items():
        # Calcular similitud coseno
        sim = co_ocurrencias_ij / (√frecuencia_i × √frecuencia_j)
        
        # Guardar solo si el producto tiene suficiente soporte
        if frecuencia_i >= MIN_SUPPORT and frecuencia_j >= MIN_SUPPORT:
            similitudes.append((producto_j, sim))
```

### Paso 4: Guardar Matriz de Similitudes

Resultado final: Un diccionario donde cada producto tiene sus "vecinos más similares"

```python
item_sim = {
    101: [
        (205, 0.336),  # Producto 205 con similitud 0.336
        (305, 0.245),  # Producto 305 con similitud 0.245
        (150, 0.198),  # Producto 150 con similitud 0.198
        ...            # Top 100 productos más similares
    ],
    205: [
        (305, 0.412),  # Producto 305 con similitud 0.412
        (401, 0.389),  # Producto 401 con similitud 0.389
        (101, 0.336),  # Producto 101 con similitud 0.336
        ...
    ],
    ...
}
```

**Se guarda en**: `models/item_sim.pkl`

---

## 🚀 Fase 2: Generación de Recomendaciones (`reco_service_stream.py`)

### Paso 1: Recibir Nueva Venta
```python
# Cuando llega una nueva venta a Kafka
venta_nueva = {
    "sale_id": 9999,
    "customer_id": 123,
    "basket_products": [101, 205]  # El cliente compró productos 101 y 205
}
```

### Paso 2: Buscar Productos Similares para Cada Producto en el Carrito

```python
carrito = [101, 205]

# Para producto 101:
vecinos_101 = item_sim.get(101, [])
# Resultado: [(205, 0.336), (305, 0.245), (150, 0.198), ...]

# Para producto 205:
vecinos_205 = item_sim.get(205, [])
# Resultado: [(305, 0.412), (401, 0.389), (101, 0.336), ...]
```

### Paso 3: Acumular Scores (Sumar Similitudes)

Si un producto aparece como similar a MÚLTIPLES productos del carrito, se suma su score:

```python
scores = {}

# Productos similares a 101:
for producto, sim in vecinos_101:
    if producto not in carrito:  # No recomendar lo que ya compró
        scores[producto] = scores.get(producto, 0) + sim

# Productos similares a 205:
for producto, sim in vecinos_205:
    if producto not in carrito:
        scores[producto] = scores.get(producto, 0) + sim

# Resultado:
scores = {
    305: 0.245 + 0.412 = 0.657,  # Muy recomendado (aparece en ambos)
    150: 0.198 + 0.000 = 0.198,  # Recomendado por 101
    401: 0.000 + 0.389 = 0.389,  # Recomendado por 205
    ...
}
```

### Paso 4: Seleccionar Top-N Recomendaciones

```python
# Ordenar por score descendente y tomar los top 5
recomendaciones = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

# Resultado final:
recomendaciones = [
    (305, 0.657),  # Producto 305 - Score más alto
    (401, 0.389),  # Producto 401
    (150, 0.198),  # Producto 150
    ...
]
```

---

## 💡 Ejemplo Práctico Completo

### Escenario:
Imagina una tienda de electrónica con estas ventas históricas:

```
Venta 1: [iPhone, AirPods]
Venta 2: [iPhone, Funda iPhone]
Venta 3: [iPad, Funda iPad]
Venta 4: [iPhone, AirPods, Funda iPhone]
Venta 5: [iPad, Apple Pencil]
Venta 6: [iPhone, iPad]
```

### Entrenamiento:

**Co-ocurrencias**:
```
iPhone aparece con:
  - AirPods: 2 veces (ventas 1 y 4)
  - Funda iPhone: 2 veces (ventas 2 y 4)
  - iPad: 1 vez (venta 6)

iPad aparece con:
  - Funda iPad: 1 vez
  - Apple Pencil: 1 vez
  - iPhone: 1 vez
```

**Similitudes calculadas** (simplificado):
```
iPhone:
  - AirPods: 0.45
  - Funda iPhone: 0.42
  - iPad: 0.25

iPad:
  - Apple Pencil: 0.50
  - Funda iPad: 0.35
  - iPhone: 0.25
```

### Recomendación en Tiempo Real:

**Nueva venta**: Cliente compra `[iPhone]`

**Proceso**:
1. Buscar vecinos de iPhone: `[(AirPods, 0.45), (Funda iPhone, 0.42), (iPad, 0.25)]`
2. Filtrar: No recomendar iPhone (ya lo compró)
3. Resultado: 
   ```
   Recomendación 1: AirPods (score: 0.45)
   Recomendación 2: Funda iPhone (score: 0.42)
   Recomendación 3: iPad (score: 0.25)
   ```

**Nueva venta**: Cliente compra `[iPhone, iPad]`

**Proceso**:
1. Vecinos de iPhone: `[(AirPods, 0.45), (Funda iPhone, 0.42), (iPad, 0.25)]`
2. Vecinos de iPad: `[(Apple Pencil, 0.50), (Funda iPad, 0.35), (iPhone, 0.25)]`
3. Acumular scores:
   ```
   AirPods: 0.45 (solo de iPhone)
   Funda iPhone: 0.42 (solo de iPhone)
   Apple Pencil: 0.50 (solo de iPad)
   Funda iPad: 0.35 (solo de iPad)
   ```
4. Resultado final:
   ```
   Recomendación 1: Apple Pencil (score: 0.50)
   Recomendación 2: AirPods (score: 0.45)
   Recomendación 3: Funda iPhone (score: 0.42)
   Recomendación 4: Funda iPad (score: 0.35)
   ```

---

## ⚙️ Hiperparámetros del Modelo

| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| `MIN_SUPPORT` | 5 | Un producto debe aparecer en al menos 5 ventas para ser considerado |
| `TOP_SIM_PER_ITEM` | 100 | Cada producto guarda máximo 100 productos similares |
| `RECENCY_HALFLIFE_MONTHS` | 6 | Las ventas antiguas tienen menos peso (mitad cada 6 meses) |
| `TOP_N` | 5 | Se recomiendan máximo 5 productos por venta |

---

## 🔄 Flujo Completo del Sistema

```
┌─────────────────────────────────────────────────────────┐
│ FASE 1: ENTRENAMIENTO (Una vez o periódicamente)       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MongoDB (sales_items)                                 │
│       │                                                 │
│       ▼                                                 │
│  model_train_reco.py                                    │
│   1. Lee todas las ventas                              │
│   2. Calcula co-ocurrencias                            │
│   3. Calcula similitudes (coseno)                      │
│   4. Guarda item_sim.pkl                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
              models/item_sim.pkl
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ FASE 2: RECOMENDACIONES (Tiempo Real)                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Kafka (erp.sales) → Nueva venta                       │
│       │                                                 │
│       ▼                                                 │
│  reco_service_stream.py                                 │
│   1. Recibe venta                                      │
│   2. Obtiene productos del carrito                     │
│   3. Busca vecinos similares en item_sim.pkl           │
│   4. Acumula scores                                    │
│   5. Selecciona top-5                                  │
│   6. Enriquece con nombres de productos                │
│   7. Guarda en MongoDB                                 │
│   8. Publica en Kafka (erp.recommendations)            │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
         Dashboard (print_recommendations_consumer.py)
```

---

## 📈 Ventajas de este Algoritmo

✅ **Simplicidad**: Fácil de entender e implementar  
✅ **Eficiencia**: Rápido en tiempo real (solo búsquedas en diccionario)  
✅ **Escalabilidad**: No necesita datos del usuario, solo de productos  
✅ **Interpretabilidad**: Se puede explicar por qué se recomienda algo  
✅ **Cold Start**: Funciona desde la primera venta con datos históricos  

---

## 🎓 Resumen

1. **Entrenamiento**: Analiza todo el histórico para encontrar patrones de productos que se compran juntos
2. **Modelo**: Guarda una matriz de similitudes (producto → productos similares)
3. **Recomendación**: Para una nueva venta, busca productos similares a los del carrito y recomienda los más similares

**Fórmula clave**: 
> "Si compraste A y B juntos, y otros compraron A con C, entonces te recomendamos C"



