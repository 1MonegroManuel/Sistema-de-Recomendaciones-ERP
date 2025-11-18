# reco_dashboard.py
# Dashboard de Streamlit para visualizar recomendaciones en tiempo real

import streamlit as st
import json
import time
from datetime import datetime
from kafka import KafkaConsumer
from pymongo import MongoClient
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.config import KAFKA_BOOTSTRAP_SERVERS, MONGODB_CONNECTION_STRING, MONGODB_DATABASE
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuración
BROKER = KAFKA_BOOTSTRAP_SERVERS
TOPIC = "erp.recommendations"
MONGO_URI = MONGODB_CONNECTION_STRING
DB_NAME = MONGODB_DATABASE
RECO_COLL = "recommendations"

# Configurar página de Streamlit
st.set_page_config(
    page_title="Dashboard de Recomendaciones",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("🎯 Dashboard de Recomendaciones - Machine Learning")
st.caption("Visualización en tiempo real de recomendaciones generadas por IA")
st.markdown("---")

# Inicializar estado de sesión para almacenar recomendaciones
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = []
if 'total_received' not in st.session_state:
    st.session_state.total_received = 0
if 'consumer' not in st.session_state:
    st.session_state.consumer = None
if 'data_source' not in st.session_state:
    st.session_state.data_source = "⏳ Detectando..."
if 'last_mongo_check' not in st.session_state:
    st.session_state.last_mongo_check = 0

# Sidebar
st.sidebar.header("🔧 Configuración")
st.sidebar.caption("Control del dashboard de recomendaciones")

# Opciones
auto_refresh = st.sidebar.checkbox("🔄 Auto-actualizar cada 10 segundos", value=False)
max_recommendations = st.sidebar.slider("Máximo de recomendaciones a mostrar", 10, 100, 50, 10)
refresh_manual = st.sidebar.button("🔄 Actualizar Ahora", type="primary", use_container_width=True)
clear_data = st.sidebar.button("🗑️ Limpiar Datos", use_container_width=True)
reset_offset = st.sidebar.button("🔄 Resetear Offset (leer desde el principio)", use_container_width=True)

if clear_data:
    st.session_state.recommendations = []
    st.session_state.total_received = 0
    st.session_state.last_mongo_check = 0
    st.rerun()

if refresh_manual:
    st.session_state.last_mongo_check = 0
    st.session_state['has_read_once'] = False
    st.rerun()

if reset_offset:
    # Cerrar consumer existente si hay
    if 'consumer' in st.session_state and st.session_state.consumer:
        try:
            st.session_state.consumer.close()
        except:
            pass
    st.session_state.consumer = None
    st.session_state['has_read_once'] = False
    # Limpiar el cache del consumer para forzar reconexión con nuevo group_id
    create_kafka_consumer.clear()
    # Cambiar el group_id temporalmente para resetear el offset
    import time
    st.session_state['reset_group_id'] = f"reco-dashboard-reset-{int(time.time())}"
    st.success("✅ Offset reseteado. Reconectando con nuevo group_id...")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 Asegúrate de que 'reco_service_stream.py' esté corriendo en otra terminal")

# Información de debug
st.sidebar.markdown("---")
st.sidebar.header("🔍 Debug")
if st.session_state.consumer:
    try:
        # Verificar asignaciones de particiones
        assignments = st.session_state.consumer.assignment()
        if assignments:
            st.sidebar.success(f"✅ Suscrito a {len(assignments)} partición(es)")
            # Obtener información de offsets
            end_offsets = st.session_state.consumer.end_offsets(assignments)
            total_messages_available = 0
            messages_behind = 0
            
            # Mostrar información de posición en cada partición
            for tp in assignments:
                try:
                    position = st.session_state.consumer.position(tp)
                    end = end_offsets.get(tp, 0)
                    available = end - position
                    total_messages_available += end
                    messages_behind += max(0, available)
                    
                    status = "📊" if available == 0 else "📨"
                    st.sidebar.caption(f"  {status} {tp.topic}[{tp.partition}]: offset {position}/{end} ({available} pendientes)")
                except:
                    pass
            
            # Mostrar resumen
            if messages_behind > 0:
                st.sidebar.info(f"📨 {messages_behind} mensaje(s) disponible(s) para leer")
            elif total_messages_available == 0:
                st.sidebar.warning("⚠️ El tópico está vacío. Verifica que `reco_service_stream.py` esté enviando mensajes.")
            else:
                st.sidebar.info("✅ Todos los mensajes han sido leídos")
        else:
            st.sidebar.warning("⚠️ Sin asignaciones de particiones")
    except Exception as e:
        st.sidebar.error(f"Error en debug: {e}")

# Función para conectar a Kafka (con cache para mantener el consumer entre reruns)
@st.cache_resource
def create_kafka_consumer(_group_id=None):
    """Crea un consumer de Kafka"""
    try:
        # Usar el group_id proporcionado o el fijo por defecto
        group_id = _group_id if _group_id else "reco-dashboard-streamlit"
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
            auto_offset_reset="earliest",  # Leer desde el principio si no hay offset guardado
            enable_auto_commit=True,
            group_id=group_id,
            consumer_timeout_ms=2000,  # Timeout corto para no bloquear Streamlit
            max_poll_records=50  # Leer hasta 50 mensajes a la vez para mejor rendimiento
        )
        # Verificar que realmente se conectó probando obtener metadata
        consumer.topics()
        # Esperar a que el consumer se suscriba correctamente
        time.sleep(1)
        return consumer
    except Exception as e:
        return None

# Función para conectar a MongoDB (con cache)
@st.cache_resource
def create_mongo_client():
    """Crea una conexión a MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        return client[DB_NAME]
    except Exception as e:
        return None

def read_recommendations_from_mongo(db, limit=50):
    """Lee recomendaciones de MongoDB ordenadas por fecha de creación (más recientes primero)"""
    try:
        if db is None:
            return []
        recommendations = list(
            db[RECO_COLL].find()
            .sort("created_at", -1)
            .limit(limit)
        )
        # Convertir ObjectId a string para serialización JSON
        for rec in recommendations:
            if '_id' in rec:
                rec['_id'] = str(rec['_id'])
            if 'created_at' not in rec and 'timestamp' in rec:
                rec['created_at'] = rec['timestamp']
        return recommendations
    except Exception as e:
        st.error(f"Error leyendo de MongoDB: {e}")
        return []

@st.cache_resource
def load_products_cache(_db):
    """Carga todos los productos de MongoDB y crea un diccionario product_id -> name"""
    try:
        if _db is None:
            return {}
        products = list(_db.products.find({}, {"product_id": 1, "name": 1, "category": 1, "unit_price": 1}))
        # Crear diccionario product_id -> {name, category, unit_price}
        product_dict = {}
        for p in products:
            pid = int(p.get("product_id", 0))
            product_dict[pid] = {
                "name": p.get("name", f"Producto #{pid}"),
                "category": p.get("category", "Sin categoría"),
                "unit_price": p.get("unit_price", 0.0)
            }
        return product_dict
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
        return {}

@st.cache_resource
def load_customers_cache(_db):
    """Carga todos los clientes de MongoDB y crea un diccionario customer_id -> name"""
    try:
        if _db is None:
            return {}
        customers = list(_db.customers.find({}, {"customer_id": 1, "first_name": 1, "last_name": 1, "email": 1}))
        # Crear diccionario customer_id -> {name, email}
        customer_dict = {}
        for c in customers:
            cid = int(c.get("customer_id", 0))
            first_name = c.get("first_name", "")
            last_name = c.get("last_name", "")
            customer_dict[cid] = {
                "name": f"{first_name} {last_name}".strip() or f"Cliente #{cid}",
                "email": c.get("email", "N/A")
            }
        return customer_dict
    except Exception as e:
        return {}

def get_sale_details(_db, sale_id):
    """Obtiene los detalles completos de una venta desde MongoDB"""
    try:
        if _db is None:
            return None
        sale = _db.sales.find_one({"sale_id": sale_id})
        return sale
    except Exception as e:
        return None

def get_sale_items(_db, sale_id):
    """Obtiene los items de una venta desde MongoDB"""
    try:
        if _db is None:
            return []
        items = list(_db.sales_items.find({"sale_id": sale_id}))
        return items
    except Exception as e:
        return []

# Métricas principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📨 Total Recomendaciones", f"{st.session_state.total_received:,}")

with col2:
    st.metric("📊 En Pantalla", len(st.session_state.recommendations))

with col3:
    if st.session_state.recommendations:
        latest_time = st.session_state.recommendations[0].get('timestamp', datetime.now().isoformat())
        st.metric("🕒 Última Recomendación", latest_time[:19] if len(latest_time) > 19 else latest_time)
    else:
        st.metric("🕒 Última Recomendación", "Esperando...")

# Intentar conectar a Kafka ANTES de mostrar métricas
consumer = None
connection_error = None
try:
    # Usar reset_group_id si está disponible (después de resetear offset)
    group_id_to_use = st.session_state.get('reset_group_id', None)
    if group_id_to_use:
        # Limpiar el reset_group_id después de usarlo
        del st.session_state['reset_group_id']
    
    consumer = create_kafka_consumer(group_id_to_use)
    if consumer:
        st.session_state.consumer = consumer
        st.session_state.kafka_status = "✅ Conectado"
    else:
        st.session_state.consumer = None
        st.session_state.kafka_status = "❌ Desconectado"
except Exception as e:
    connection_error = str(e)
    st.session_state.consumer = None
    st.session_state.kafka_status = "❌ Error"

# Inicializar estado si no existe
if 'kafka_status' not in st.session_state:
    st.session_state.kafka_status = "⏳ Conectando..."

with col4:
    st.metric("🔌 Estado Kafka", st.session_state.kafka_status)

st.markdown("---")

# Mostrar fuente de datos actual
if st.session_state.data_source != "⏳ Detectando...":
    st.info(f"📊 **Fuente de datos:** {st.session_state.data_source}")

st.markdown("---")

# Conectar a MongoDB como respaldo
mongo_db = create_mongo_client()
mongo_available = mongo_db is not None

# Cargar cache de productos y clientes (para mostrar nombres en lugar de solo IDs)
products_cache = load_products_cache(mongo_db) if mongo_available else {}
customers_cache = load_customers_cache(mongo_db) if mongo_available else {}

# Leer mensajes si hay consumer de Kafka
kafka_has_messages = False
if consumer:
    # Verificar si hay mensajes disponibles en el tópico
    try:
        from kafka import TopicPartition
        assignments = consumer.assignment()
        if assignments:
            # Obtener el último offset disponible (end_offsets)
            end_offsets = consumer.end_offsets(assignments)
            # Obtener la posición actual
            current_positions = {tp: consumer.position(tp) for tp in assignments}
            
            # Verificar si hay mensajes pendientes
            messages_available = False
            for tp in assignments:
                current = current_positions.get(tp, 0)
                end = end_offsets.get(tp, 0)
                if current < end:
                    messages_available = True
                    break
            
            # Si hay mensajes disponibles pero no se están leyendo, forzar lectura desde la posición actual
            if messages_available and not st.session_state.get('has_read_once', False):
                # Asegurar que estamos en la posición correcta
                for tp in assignments:
                    if current_positions.get(tp, 0) < end_offsets.get(tp, 0):
                        # Ya estamos en la posición correcta, solo necesitamos leer
                        pass
        st.session_state['has_read_once'] = True
    except Exception as e:
        # Si falla la verificación, continuar de todas formas
        pass
    
    # Leer mensajes nuevos - intentar varias veces para asegurar que lee
    new_recommendations = []
    total_msgs = 0
    try:
        # Intentar leer múltiples veces para asegurar que se capturan todos los mensajes
        for attempt in range(5):  # Intentar 5 veces con más paciencia
            messages = consumer.poll(timeout_ms=2000)  # Aumentar timeout
            
            if messages:
                for topic_partition, msgs in messages.items():
                    total_msgs += len(msgs)
                    for msg in msgs:
                        try:
                            rec_data = msg.value
                            if rec_data and isinstance(rec_data, dict):
                                # Asegurarse de que tiene los campos esperados
                                if 'sale_id' in rec_data or 'recommendations' in rec_data:
                                    rec_data['_received_at'] = datetime.now().isoformat()
                                    new_recommendations.append(rec_data)
                                    st.session_state.total_received += 1
                        except Exception as e:
                            # No mostrar warning para cada mensaje individual
                            pass
            else:
                # Si no hay mensajes en este intento y ya intentamos varias veces, salir
                if attempt >= 2:  # Después de 2 intentos sin mensajes, salir
                    break
        
        # Agregar nuevas recomendaciones al inicio
        if new_recommendations:
            kafka_has_messages = True
            st.session_state.data_source = "📨 Kafka (tiempo real)"
            st.session_state.recommendations = new_recommendations + st.session_state.recommendations
            # Limitar el número de recomendaciones mostradas
            st.session_state.recommendations = st.session_state.recommendations[:max_recommendations]
            
            # Mostrar notificación de nuevas recomendaciones
            st.success(f"✅ {len(new_recommendations)} nueva(s) recomendación(es) recibida(s) de Kafka ({total_msgs} mensaje(s) leído(s))")
        elif total_msgs > 0:
            # Se leyeron mensajes pero no se pudieron procesar
            st.warning(f"⚠️ Se leyeron {total_msgs} mensaje(s) pero no se pudieron procesar")
    except Exception as e:
        st.warning(f"⚠️ Error leyendo mensajes de Kafka: {e}")
        # No resetear el consumer, solo mostrar el error
else:
    # No se pudo conectar
    st.session_state.consumer = None

# ✅ Si Kafka no tiene mensajes, leer de MongoDB como respaldo
if not kafka_has_messages and mongo_available:
    try:
        if consumer:
            assignments = consumer.assignment()
            if assignments:
                end_offsets = consumer.end_offsets(assignments)
                current_positions = {tp: consumer.position(tp) for tp in assignments}
                
                # Verificar si realmente hay mensajes pendientes
                has_pending = False
                for tp in assignments:
                    if current_positions.get(tp, 0) < end_offsets.get(tp, 0):
                        has_pending = True
                        break
                
                if not has_pending:
                    # Kafka está vacío, usar MongoDB
                    st.session_state.data_source = "💾 MongoDB (respaldo)"
                    
                    # Leer de MongoDB solo cada 10 segundos (o cuando se presione el botón manual)
                    current_time = time.time()
                    force_refresh = st.session_state.last_mongo_check == 0
                    time_since_last_check = current_time - st.session_state.last_mongo_check
                    
                    if force_refresh or time_since_last_check >= 10:
                        mongo_recommendations = read_recommendations_from_mongo(mongo_db, limit=max_recommendations)
                        if mongo_recommendations:
                            st.session_state.recommendations = mongo_recommendations
                            st.session_state.total_received = len(mongo_recommendations)
                            st.session_state.last_mongo_check = current_time
                            if force_refresh:
                                st.success(f"✅ {len(mongo_recommendations)} recomendación(es) cargada(s) de MongoDB")
                        else:
                            st.session_state.last_mongo_check = current_time
                            if force_refresh:
                                st.info("ℹ️ No hay recomendaciones disponibles en MongoDB aún")
                    else:
                        time_remaining = 10 - int(time_since_last_check)
                        if time_remaining > 0:
                            st.session_state.data_source = f"💾 MongoDB (próxima actualización en {time_remaining}s)"
                else:
                    st.session_state.data_source = "📨 Kafka (leyendo...)"
    except Exception as e:
        # Si hay error verificando Kafka, intentar MongoDB
        if mongo_available:
            st.session_state.data_source = "💾 MongoDB (respaldo)"
            mongo_recommendations = read_recommendations_from_mongo(mongo_db, limit=max_recommendations)
            if mongo_recommendations:
                st.session_state.recommendations = mongo_recommendations
                st.session_state.total_received = len(mongo_recommendations)
elif not mongo_available and not kafka_has_messages:
    st.session_state.data_source = "❌ Sin conexión"

# Mostrar warning solo si no se pudo conectar Y no hay recomendaciones previas
if not st.session_state.consumer and len(st.session_state.recommendations) == 0:
    st.warning("⚠️ No se pudo conectar a Kafka. Verifica que:")
    st.markdown("""
    1. ✅ Kafka esté corriendo (`docker-compose up -d`)
    2. ✅ `reco_service_stream.py` esté generando recomendaciones
    3. ✅ El broker esté accesible en `{BROKER}`
    """.format(BROKER=BROKER))

# Mostrar recomendaciones
if st.session_state.recommendations:
    st.header("📋 Recomendaciones Recientes")
    
    # Tabs para diferentes vistas
    tab1, tab2, tab3 = st.tabs(["📋 Lista", "📊 Estadísticas", "🔍 Detalles"])
    
    with tab1:
        st.subheader("Lista de Recomendaciones")
        
        # Mostrar recomendaciones en tarjetas
        for idx, rec in enumerate(st.session_state.recommendations[:max_recommendations]):
            sale_id = rec.get('sale_id', 'N/A')
            timestamp = rec.get('timestamp', 'N/A')[:19] if rec.get('timestamp') else 'N/A'
            
            # Obtener información completa de la venta desde MongoDB
            sale_details = None
            sale_items = []
            if mongo_available and sale_id != 'N/A':
                try:
                    sale_details = get_sale_details(mongo_db, int(sale_id))
                    sale_items = get_sale_items(mongo_db, int(sale_id))
                except:
                    pass
            
            with st.expander(f"🛒 Venta #{sale_id} - {timestamp}", expanded=(idx < 3)):
                # ========== SECCIÓN 1: INFORMACIÓN DE LA VENTA ==========
                st.subheader("📋 Información de la Venta")
                
                # Obtener información de la venta (priorizar customer_id del payload, luego de sale_details)
                customer_id = rec.get('customer_id') or (sale_details.get('customer_id') if sale_details else None)
                store_id = sale_details.get('store_id', 'N/A') if sale_details else 'N/A'
                payment_type = sale_details.get('payment_type', 'N/A') if sale_details else 'N/A'
                total_amount = sale_details.get('total_amount', 0.0) if sale_details else 0.0
                items_count = sale_details.get('items_count', len(rec.get('basket_products', []))) if sale_details else len(rec.get('basket_products', []))
                
                # Obtener nombre del cliente (con múltiples intentos)
                customer_name = "N/A"
                customer_email = "N/A"
                if customer_id:
                    try:
                        # Intentar convertir a int
                        customer_id_int = int(customer_id) if customer_id else None
                        if customer_id_int:
                            # Primero buscar en cache
                            if customer_id_int in customers_cache:
                                customer_info = customers_cache[customer_id_int]
                                customer_name = customer_info.get('name', f'Cliente #{customer_id_int}')
                                customer_email = customer_info.get('email', 'N/A')
                            else:
                                # Si no está en cache, intentar buscar directamente en MongoDB
                                if mongo_available:
                                    try:
                                        customer_doc = mongo_db.customers.find_one({"customer_id": customer_id_int}, {"first_name": 1, "last_name": 1, "email": 1})
                                        if customer_doc:
                                            first_name = customer_doc.get("first_name", "")
                                            last_name = customer_doc.get("last_name", "")
                                            customer_name = f"{first_name} {last_name}".strip() or f'Cliente #{customer_id_int}'
                                            customer_email = customer_doc.get("email", "N/A")
                                            # Actualizar cache para futuras consultas
                                            customers_cache[customer_id_int] = {
                                                "name": customer_name,
                                                "email": customer_email
                                            }
                                        else:
                                            customer_name = f'Cliente #{customer_id_int}'
                                    except Exception as e:
                                        customer_name = f'Cliente #{customer_id_int}'
                                else:
                                    customer_name = f'Cliente #{customer_id_int}'
                    except (ValueError, TypeError) as e:
                        # Si no se puede convertir a int, mostrar el valor original
                        customer_name = f'Cliente {customer_id}'
                
                # Mostrar información de la venta en columnas
                col_sale1, col_sale2, col_sale3, col_sale4 = st.columns(4)
                
                with col_sale1:
                    st.metric("👤 Cliente", customer_name)
                    if customer_id:
                        st.caption(f"ID: {customer_id}")
                
                with col_sale2:
                    st.metric("🏪 Tienda", store_id)
                    st.caption(f"💰 Total: ${total_amount:.2f}" if total_amount > 0 else "")
                
                with col_sale3:
                    st.metric("💳 Pago", payment_type)
                    st.caption(f"📦 Items: {items_count}")
                
                with col_sale4:
                    st.metric("📅 Fecha", timestamp)
                    st.caption(f"🤖 Algoritmo: {rec.get('algo', 'N/A')}")
                
                if customer_email != "N/A":
                    st.caption(f"📧 Email: {customer_email}")
                
                st.markdown("---")
                
                # ========== SECCIÓN 2: PRODUCTOS QUE COMPRÓ EL CLIENTE ==========
                st.subheader("🛍️ Productos que Compró el Cliente")
                
                basket = rec.get('basket_products', [])
                
                if sale_items:
                    # Mostrar items de la venta con detalles completos
                    basket_data = []
                    for item in sale_items:
                        pid = int(item.get('product_id', 0))
                        quantity = item.get('quantity', 1)
                        unit_price = item.get('unit_price', 0.0)
                        net_amount = item.get('net_amount', unit_price * quantity)
                        
                        # Obtener información del producto
                        product_info = products_cache.get(pid, {})
                        product_name = product_info.get('name', f'Producto #{pid}')
                        category = product_info.get('category', 'Sin categoría')
                        
                        basket_data.append({
                            'Producto ID': pid,
                            'Nombre': product_name,
                            'Categoría': category,
                            'Cantidad': quantity,
                            'Precio Unit.': f"${unit_price:.2f}",
                            'Subtotal': f"${net_amount:.2f}"
                        })
                    
                    if basket_data:
                        basket_df = pd.DataFrame(basket_data)
                        st.dataframe(basket_df, use_container_width=True, hide_index=True)
                        
                        # Calcular total del carrito
                        total_basket = sum(float(item.get('net_amount', 0)) for item in sale_items)
                        st.info(f"💰 **Total del Carrito:** ${total_basket:.2f}")
                    else:
                        st.warning("No se encontraron detalles de los productos comprados")
                elif basket:
                    # Fallback: mostrar solo los IDs del basket
                    basket_list = []
                    for pid in basket:
                        pid_int = int(pid) if isinstance(pid, (int, float)) else int(pid)
                        product_info = products_cache.get(pid_int, {})
                        basket_list.append({
                            'Producto ID': pid_int,
                            'Nombre': product_info.get('name', f'Producto #{pid_int}'),
                            'Categoría': product_info.get('category', 'Sin categoría')
                        })
                    
                    if basket_list:
                        basket_df = pd.DataFrame(basket_list)
                        st.dataframe(basket_df, use_container_width=True, hide_index=True)
                        st.caption("⚠️ Información limitada: no se encontraron detalles de precios en la venta")
                    else:
                        st.write("N/A")
                else:
                    st.warning("No hay productos en la cesta")
                
                st.markdown("---")
                
                # ========== SECCIÓN 3: RECOMENDACIONES DEL MACHINE LEARNING ==========
                st.subheader("🤖 Recomendaciones del Machine Learning")
                recommendations = rec.get('recommendations', [])
                
                # Verificar que recommendations sea una lista válida
                if not isinstance(recommendations, list):
                    recommendations = []
                
                if recommendations and len(recommendations) > 0:
                    # Crear DataFrame para mostrar recomendaciones con nombres y métricas de ML
                    # ✅ Primero intentar usar nombres de las recomendaciones (si fueron enriquecidas)
                    # ✅ Si no, hacer lookup desde el cache de productos
                    rec_list = []
                    for r in recommendations:
                        pid = int(r.get('product_id', 0))
                        # Compatibilidad: aceptar "relevancia" o "score"
                        relevancia = r.get('relevancia', r.get('score', 0))
                        
                        # Obtener métricas de ML en porcentajes (si están disponibles)
                        relevancia_percentage = r.get('relevancia_percentage', r.get('score_percentage', None))
                        confidence_percentage = r.get('confidence_percentage', None)
                        ranking_percentage = r.get('ranking_percentage', None)
                        ranking = r.get('ranking', len(rec_list) + 1)
                        
                        # Si no están las métricas en porcentajes, calcularlas
                        if relevancia_percentage is None:
                            # Normalizar relevancia a porcentaje (0-100%)
                            relevancias_all = [rec.get('relevancia', rec.get('score', 0)) for rec in recommendations]
                            max_relevancia = max(relevancias_all) if relevancias_all else 1.0
                            min_relevancia = min(relevancias_all) if relevancias_all else 0.0
                            relevancia_range = max_relevancia - min_relevancia if max_relevancia > min_relevancia else 1.0
                            relevancia_percentage = ((relevancia - min_relevancia) / relevancia_range * 100.0) if relevancia_range > 0 else 0.0
                        
                        if confidence_percentage is None:
                            confidence_percentage = min(100.0, relevancia_percentage * 1.2) if relevancia_percentage else 0.0
                        
                        if ranking_percentage is None:
                            total_recs = len(recommendations)
                            ranking_percentage = ((total_recs - ranking + 1) / total_recs * 100.0) if total_recs > 0 else 0.0
                        
                        # Intentar obtener nombre desde la recomendación enriquecida
                        product_name = r.get('product_name') or r.get('name')
                        category = r.get('category')
                        
                        # Si no está enriquecida, usar el cache de productos
                        if not product_name:
                            product_info = products_cache.get(pid, {})
                            product_name = product_info.get('name', f'Producto #{pid}')
                            if not category:
                                category = product_info.get('category', 'Sin categoría')
                        
                        rec_list.append({
                            'Ranking': ranking,
                            'Producto ID': pid,
                            'Nombre del Producto': product_name,
                            'Categoría': category or 'Sin categoría',
                            'Relevancia': round(relevancia, 4),
                            'Relevancia %': f"{round(relevancia_percentage, 2)}%",
                            'Confianza %': f"{round(confidence_percentage, 2)}%",
                            'Ranking %': f"{round(ranking_percentage, 2)}%"
                        })
                    
                    rec_df = pd.DataFrame(rec_list)
                    rec_df = rec_df.sort_values('Relevancia', ascending=False)
                    rec_df['Ranking'] = range(1, len(rec_df) + 1)  # Recalcular ranking después de ordenar
                    
                    # Recalcular ranking_percentage basado en el nuevo ranking
                    total_recs = len(rec_df)
                    rec_df['Ranking %'] = rec_df['Ranking'].apply(
                        lambda r: f"{round(((total_recs - r + 1) / total_recs * 100.0) if total_recs > 0 else 0.0, 2)}%"
                    )
                    
                    # Reordenar columnas con métricas de ML
                    rec_df = rec_df[['Ranking', 'Producto ID', 'Nombre del Producto', 'Categoría', 'Relevancia', 'Relevancia %', 'Confianza %', 'Ranking %']]
                    
                    # Mostrar como tabla
                    st.dataframe(rec_df, use_container_width=True, hide_index=True)
                    
                    # Gráfico de barras de relevancia en porcentajes con nombres
                    # Convertir Relevancia % a número para el gráfico
                    rec_df['Relevancia_Percentage_Num'] = rec_df['Relevancia %'].str.replace('%', '').astype(float)
                    
                    fig = px.bar(
                        rec_df, 
                        x='Nombre del Producto', 
                        y='Relevancia_Percentage_Num',
                        title=f"Relevancia de Recomendaciones (Porcentajes) - Venta #{sale_id}",
                        labels={'Nombre del Producto': 'Producto', 'Relevancia_Percentage_Num': 'Relevancia (%)'},
                        color='Relevancia_Percentage_Num',
                        color_continuous_scale='viridis',
                        hover_data={'Producto ID': True, 'Categoría': True, 'Relevancia': True, 'Confianza %': True}
                    )
                    fig.update_layout(
                        template="plotly_white", 
                        height=350,
                        xaxis_tickangle=-45,  # Rotar etiquetas para mejor legibilidad
                        xaxis_title="",
                        yaxis_title="Relevancia (%)"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Mostrar estadísticas rápidas con métricas de ML
                    col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
                    with col_stats1:
                        avg_relevancia_pct = rec_df['Relevancia_Percentage_Num'].mean()
                        st.metric("📊 Relevancia Promedio", f"{avg_relevancia_pct:.2f}%")
                    with col_stats2:
                        max_relevancia_pct = rec_df['Relevancia_Percentage_Num'].max()
                        st.metric("📈 Relevancia Máxima", f"{max_relevancia_pct:.2f}%")
                    with col_stats3:
                        # Calcular confianza promedio
                        conf_avg = rec_df['Confianza %'].str.replace('%', '').astype(float).mean()
                        st.metric("🎯 Confianza Promedio", f"{conf_avg:.2f}%")
                    with col_stats4:
                        st.metric("🎯 Total Recomendaciones", len(rec_df))
                    
                    # Mostrar métricas adicionales por producto (en tarjetas expandibles)
                    st.markdown("### 📊 Métricas de ML por Producto")
                    for idx, row in rec_df.iterrows():
                        with st.expander(f"📦 {row['Nombre del Producto']} (#{row['Ranking']})", expanded=False):
                            col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                            with col_met1:
                                st.metric("Relevancia", f"{row['Relevancia']:.4f}")
                            with col_met2:
                                st.metric("Relevancia (%)", row['Relevancia %'])
                            with col_met3:
                                st.metric("Confianza (%)", row['Confianza %'])
                            with col_met4:
                                st.metric("Ranking (%)", row['Ranking %'])
                else:
                    # Mostrar información más detallada cuando no hay recomendaciones
                    basket_products = rec.get('basket_products', [])
                    if basket_products:
                        st.warning(f"⚠️ No se generaron recomendaciones para esta venta. Esto puede deberse a:")
                        st.markdown("""
                        - Los productos en el carrito no tienen suficientes relaciones de similitud en el modelo
                        - El modelo aún no ha aprendido patrones para estos productos
                        - Los productos son muy nuevos o poco frecuentes en el histórico de ventas
                        """)
                        st.info(f"📦 Productos en el carrito: {len(basket_products)} producto(s)")
                    else:
                        st.info("ℹ️ No hay productos en el carrito de esta venta, por lo que no se pueden generar recomendaciones")
                
                st.caption(f"⏰ Recibido: {rec.get('_received_at', 'N/A')[:19] if rec.get('_received_at') else 'N/A'}")
    
    with tab2:
        st.subheader("Estadísticas de Recomendaciones")
        
        if st.session_state.recommendations:
            # Análisis de recomendaciones
            all_relevancias = []
            products_recommended = []
            sales_processed = len(st.session_state.recommendations)
            
            for rec in st.session_state.recommendations:
                recommendations = rec.get('recommendations', [])
                for r in recommendations:
                    # Compatibilidad: aceptar "relevancia" o "score"
                    relevancia = r.get('relevancia', r.get('score', 0))
                    all_relevancias.append(relevancia)
                    products_recommended.append(r.get('product_id', 0))
            
            if all_relevancias:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("📊 Relevancia Promedio", f"{sum(all_relevancias) / len(all_relevancias):.4f}")
                    st.metric("📈 Relevancia Máxima", f"{max(all_relevancias):.4f}")
                    st.metric("📉 Relevancia Mínima", f"{min(all_relevancias):.4f}")
                
                with col2:
                    st.metric("🎯 Productos Únicos Recomendados", len(set(products_recommended)))
                    st.metric("📦 Total Recomendaciones", len(all_relevancias))
                    st.metric("🛒 Ventas Procesadas", sales_processed)
                
                # Histograma de relevancias
                if all_relevancias:
                    fig = px.histogram(
                        x=all_relevancias,
                        nbins=20,
                        title="Distribución de Relevancia de Recomendaciones",
                        labels={'x': 'Relevancia', 'count': 'Frecuencia'},
                        color_discrete_sequence=['#636EFA']
                    )
                    fig.update_layout(template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Top productos más recomendados
                if products_recommended:
                    from collections import Counter
                    product_counts = Counter(products_recommended)
                    
                    # Crear DataFrame con nombres de productos
                    # ✅ Intentar obtener nombres desde las recomendaciones primero
                    # Crear un diccionario de productos recomendados con sus nombres si están disponibles
                    product_names_map = {}
                    for rec in st.session_state.recommendations:
                        recommendations = rec.get('recommendations', [])
                        for r in recommendations:
                            pid = int(r.get('product_id', 0))
                            if pid not in product_names_map:
                                # Intentar obtener nombre desde la recomendación enriquecida
                                product_name = r.get('product_name') or r.get('name')
                                category = r.get('category')
                                
                                if not product_name:
                                    # Si no está enriquecida, usar el cache
                                    product_info = products_cache.get(pid, {})
                                    product_name = product_info.get('name', f'Producto #{pid}')
                                    if not category:
                                        category = product_info.get('category', 'Sin categoría')
                                
                                product_names_map[pid] = {
                                    'name': product_name,
                                    'category': category or 'Sin categoría'
                                }
                    
                    top_products_list = []
                    for pid, count in product_counts.most_common(20):
                        pid_int = int(pid)
                        # Usar el mapa de nombres creado o el cache como fallback
                        if pid_int in product_names_map:
                            product_info = product_names_map[pid_int]
                        else:
                            product_info = products_cache.get(pid_int, {})
                        
                        top_products_list.append({
                            'Producto ID': pid_int,
                            'Nombre del Producto': product_info.get('name', products_cache.get(pid_int, {}).get('name', f'Producto #{pid_int}')),
                            'Categoría': product_info.get('category', products_cache.get(pid_int, {}).get('category', 'Sin categoría')),
                            'Veces Recomendado': count
                        })
                    
                    top_products = pd.DataFrame(top_products_list)
                    
                    st.subheader("🏆 Top 20 Productos Más Recomendados")
                    
                    # Mostrar tabla con nombres
                    st.dataframe(top_products[['Producto ID', 'Nombre del Producto', 'Categoría', 'Veces Recomendado']], 
                                use_container_width=True, hide_index=True)
                    
                    # Gráfico de barras con nombres
                    fig = px.bar(
                        top_products,
                        x='Nombre del Producto',
                        y='Veces Recomendado',
                        title="Productos Más Recomendados",
                        labels={'Nombre del Producto': 'Producto', 'Veces Recomendado': 'Frecuencia'},
                        color='Veces Recomendado',
                        color_continuous_scale='plasma',
                        hover_data={'Producto ID': True, 'Categoría': True}
                    )
                    fig.update_layout(
                        template="plotly_white",
                        xaxis_tickangle=-45,  # Rotar etiquetas
                        xaxis_title="",
                        yaxis_title="Veces Recomendado"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos estadísticos disponibles aún")
    
    with tab3:
        st.subheader("Detalle Completo de Recomendaciones")
        
        # Selector de recomendación
        if st.session_state.recommendations:
            options = [
                f"Venta #{rec.get('sale_id', 'N/A')} - {rec.get('timestamp', 'N/A')[:19] if rec.get('timestamp') else 'N/A'}"
                for rec in st.session_state.recommendations
            ]
            selected = st.selectbox("Selecciona una recomendación para ver detalles", options)
            
            if selected:
                idx = options.index(selected)
                rec = st.session_state.recommendations[idx]
                
                st.json(rec)
elif not st.session_state.recommendations:
    st.info("💡 Esperando recomendaciones...")
    st.markdown("""
    **Pasos para verificar:**
    1. ✅ Verifica que `reco_service_stream.py` esté corriendo en otra terminal
    2. ✅ Verifica que `reco_service_stream.py` esté procesando ventas (debería mostrar mensajes como "📨 Recibido lote de X mensaje(s)")
    3. ✅ El dashboard intentará leer de **Kafka** primero, y si está vacío, leerá de **MongoDB** automáticamente
    4. 💡 Las recomendaciones se guardan en MongoDB en la colección `recommendations` como respaldo
    5. 💡 Si `reco_service_stream.py` ya procesó ventas antes de abrir este dashboard, el dashboard debería leerlas de MongoDB automáticamente
    6. 💡 Usa el botón "🔄 Actualizar Ahora" para forzar una actualización manual
    """)
    
    # Mostrar información adicional sobre la fuente de datos
    if st.session_state.data_source == "💾 MongoDB (respaldo)":
        st.success("✅ Leyendo de MongoDB. Si `reco_service_stream.py` está procesando ventas, las recomendaciones deberían aparecer aquí.")
    elif st.session_state.consumer and st.session_state.kafka_status == "✅ Conectado":
        st.warning("⚠️ Conectado a Kafka pero no hay mensajes en el tópico. El dashboard intentará leer de MongoDB automáticamente.")

# Auto-refresh (más lento ahora)
if auto_refresh:
    time.sleep(10)  # 10 segundos en lugar de 5
    st.rerun()

# Footer
st.markdown("---")
st.caption(f"🔄 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Dashboard de Recomendaciones ML")
