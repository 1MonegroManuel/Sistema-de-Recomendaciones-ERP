# erp_dashboard_dinamico_corregido.py
# Dashboard para datos dinámicos/tiempo real del sistema ERP
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pymongo
from datetime import datetime, timedelta
import io
import base64
import numpy as np
from config import MONGODB_CONNECTION_STRING, MONGODB_DATABASE, COLLECTIONS

# ---------- Estilo visual ----------
PLOT_TEMPLATE = "plotly_white"
COLOR_SEQ = px.colors.qualitative.Set3

# ---------- Configuración ----------
MONGO_URI = MONGODB_CONNECTION_STRING
DB_NAME = MONGODB_DATABASE

def get_mongo_data():
    """Obtiene datos de MongoDB"""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        client.admin.command('ping')
        return db
    except Exception as e:
        st.error(f"Error conectando a MongoDB: {e}")
        return None

@st.cache_data(ttl=5)  # Cache por 5 segundos para datos dinámicos
def load_dynamic_sales_data():
    """Carga datos de ventas dinámicos"""
    db = get_mongo_data()
    if db is None:
        return pd.DataFrame()
    
    # Cargar datos de ventas recientes (últimas 5000)
    data = list(db.sales.find().sort("_id", -1).limit(5000))
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Limpiar y convertir datos
    if 'sale_datetime' in df.columns:
        df['sale_datetime'] = pd.to_datetime(df['sale_datetime'], errors='coerce')
        df['fecha_venta'] = df['sale_datetime'].dt.date
        df['hora_venta'] = df['sale_datetime'].dt.hour
        df['dia_semana'] = df['sale_datetime'].dt.day_name()
        df['mes'] = df['sale_datetime'].dt.month
        df['año'] = df['sale_datetime'].dt.year
    
    # Convertir campos numéricos
    numeric_fields = ['total_amount', 'items_count', 'tax', 'discount_header', 'gross_amount', 'net_amount']
    for field in numeric_fields:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors='coerce')
    
    return df

def create_download_link(df, filename, file_type="csv"):
    """Crea enlace de descarga para DataFrame"""
    if file_type == "csv":
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar CSV</a>'
    else:  # excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        b64 = base64.b64encode(output.getvalue()).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Descargar Excel</a>'
    
    return href


def create_correlation_heatmap(data, title):
    """Crea mapa de calor de correlaciones"""
    if data.empty:
        return None
    
    # Seleccionar solo columnas numéricas
    numeric_columns = data.select_dtypes(include=[np.number]).columns
    if len(numeric_columns) < 2:
        return None
    
    # Calcular matriz de correlación
    corr_matrix = data[numeric_columns].corr()
    
    # Crear heatmap
    fig = px.imshow(
        corr_matrix,
        text_auto=True,
        aspect="auto",
        title=title,
        color_continuous_scale='RdBu_r'
    )
    
    fig.update_layout(
        xaxis_title="Variables",
        yaxis_title="Variables"
    )
    
    return fig

def get_data_statistics(data):
    """Obtiene estadísticas descriptivas de los datos"""
    if data.empty:
        return {}
    
    stats = {}
    numeric_columns = data.select_dtypes(include=[np.number]).columns
    
    for col in numeric_columns:
        clean_data = data[col].dropna()
        if not clean_data.empty:
            stats[col] = {
                'cantidad': len(clean_data),
                'promedio': clean_data.mean(),
                'desviacion': clean_data.std(),
                'minimo': clean_data.min(),
                'maximo': clean_data.max(),
                'mediana': clean_data.median(),
                'asimetria': clean_data.skew(),
                'curtosis': clean_data.kurtosis()
            }
    
    return stats

def main():
    st.set_page_config(
        page_title="Dashboard ERP Dinámico",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Título principal
    st.title("⚡ Dashboard ERP - Datos Dinámicos (Tiempo Real)")
    st.caption("Monitoreo en vivo de ventas, sucursales y métodos de pago")
    st.markdown("---")
    
    # Verificar conexión a MongoDB
    db = get_mongo_data()
    if db is None:
        st.error("❌ No se pudo conectar a MongoDB. Verifica que el servicio esté ejecutándose.")
        return
    
    st.success("✅ Conectado a MongoDB exitosamente")
    st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Cargar datos dinámicos
    sales_data = load_dynamic_sales_data()
    
    # Verificar si hay datos
    if sales_data.empty:
        st.warning("⚠️ No hay datos de ventas dinámicos disponibles.")
        return
    
    # Filtros de fechas
    st.sidebar.header("🔧 Filtros")
    st.sidebar.caption("Ajusta el rango temporal y segmenta por tienda o pago")
    
    # Filtro por rango de fechas
    if 'sale_datetime' in sales_data.columns:
        min_date = sales_data['sale_datetime'].min().date()
        max_date = sales_data['sale_datetime'].max().date()
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha Inicio", min_date)
        with col2:
            fecha_fin = st.date_input("Fecha Fin", max_date)
        
        # Aplicar filtro de fechas
        if fecha_inicio and fecha_fin:
            sales_data = sales_data[
                (sales_data['sale_datetime'].dt.date >= fecha_inicio) & 
                (sales_data['sale_datetime'].dt.date <= fecha_fin)
            ]
    
    # Filtros adicionales
    st.sidebar.subheader("🔍 Filtros Adicionales")
    
    # Filtro por tienda
    if 'store_id' in sales_data.columns:
        tiendas = ["Todas"] + sorted(sales_data['store_id'].unique().tolist())
        tienda_seleccionada = st.sidebar.selectbox("Tienda", tiendas)
        if tienda_seleccionada != "Todas":
            sales_data = sales_data[sales_data['store_id'] == tienda_seleccionada]
    
    # Filtro por tipo de pago
    if 'payment_type' in sales_data.columns:
        tipos_pago = ["Todos"] + sorted(sales_data['payment_type'].unique().tolist())
        tipo_pago_seleccionado = st.sidebar.selectbox("Tipo de Pago", tipos_pago)
        if tipo_pago_seleccionado != "Todos":
            sales_data = sales_data[sales_data['payment_type'] == tipo_pago_seleccionado]
    
    # Mostrar información de filtros
    st.info(f"📅 Mostrando {len(sales_data):,} registros de ventas")
    
    # Auto-refresh
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.info("Consejo: activa el auto-refresh para ver cambios en tiempo real")
    
    # Métricas principales
    st.header("📈 Métricas en Tiempo Real")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        ingresos_totales = sales_data['total_amount'].sum()
        st.metric("💰 Ingresos Totales", f"${ingresos_totales:,.2f}")
    
    with col2:
        total_ordenes = len(sales_data)
        st.metric("📦 Total Órdenes", f"{total_ordenes:,}")
    
    with col3:
        valor_promedio_orden = sales_data['total_amount'].mean()
        st.metric("💵 Valor Promedio por Orden", f"${valor_promedio_orden:.2f}")
    
    with col4:
        total_items = sales_data['items_count'].sum()
        st.metric("📦 Total Items Vendidos", f"{total_items:,}")
    
    st.markdown("---")
    
    # Gráficos principales
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Ventas por Día")
        if 'fecha_venta' in sales_data.columns:
            ventas_diarias = sales_data.groupby('fecha_venta').agg({
                'total_amount': 'sum',
                'sale_id': 'count'
            }).reset_index()
            ventas_diarias.columns = ['fecha_venta', 'total_ventas', 'cantidad_ordenes']
            
            fig = px.line(
                ventas_diarias,
                x='fecha_venta',
                y='total_ventas',
                title="Evolución de Ventas Diarias",
                labels={'total_ventas': 'Ventas ($)', 'fecha_venta': 'Fecha'},
                markers=True,
                template=PLOT_TEMPLATE
            )
            fig.update_traces(hovertemplate='Fecha=%{x|%Y-%m-%d}<br>Ventas=$%{y:,.2f}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("⏰ Ventas por Hora y Sucursal")
        if 'hora_venta' in sales_data.columns and 'store_id' in sales_data.columns:
            # Agrupar por hora y sucursal para crear barras apiladas
            ventas_horarias_sucursal = sales_data.groupby(['hora_venta', 'store_id']).agg({
                'total_amount': 'sum'
            }).reset_index()
            ventas_horarias_sucursal.columns = ['hora_venta', 'sucursal', 'total_ventas']
            
            # Crear gráfico de barras apiladas
            # Ordenar horas 0..23 para mejor lectura
            ventas_horarias_sucursal = ventas_horarias_sucursal.sort_values(['hora_venta','sucursal'])

            fig = px.bar(
                ventas_horarias_sucursal,
                x='hora_venta',
                y='total_ventas',
                color='sucursal',
                title="Ventas por Hora del Día - Desglosado por Sucursal",
                labels={'total_ventas': 'Ventas ($)', 'hora_venta': 'Hora', 'sucursal': 'Sucursal'},
                color_discrete_sequence=COLOR_SEQ,
                template=PLOT_TEMPLATE
            )
            
            # Personalizar el gráfico
            fig.update_layout(
                barmode='stack',
                xaxis_title="Hora del Día",
                yaxis_title="Ventas ($)",
                legend_title="Sucursal",
                height=400
            )
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=[str(h) for h in range(24)])
            fig.update_traces(hovertemplate='Hora=%{x}:00<br>Sucursal=%{legendgroup}<br>Ventas=$%{y:,.2f}<extra></extra>')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Mostrar tabla de datos
            st.subheader("📊 Desglose por Hora y Sucursal")
            tabla_resumen = ventas_horarias_sucursal.pivot_table(
                index='hora_venta', 
                columns='sucursal', 
                values='total_ventas', 
                fill_value=0
            ).round(2)
            st.dataframe(tabla_resumen, use_container_width=True)
        else:
            st.warning("No hay datos suficientes para mostrar ventas por hora y sucursal")
    
    # Análisis de tiendas
    st.subheader("🏪 Análisis por Sucursal")
    if 'store_id' in sales_data.columns:
        analisis_sucursales = sales_data.groupby('store_id').agg({
            'total_amount': ['sum', 'count', 'mean'],
            'items_count': 'sum'
        }).round(2)
        analisis_sucursales.columns = ['Total Ventas', 'Cantidad Órdenes', 'Valor Promedio', 'Total Items']
        analisis_sucursales = analisis_sucursales.reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(
                analisis_sucursales,
                values='Total Ventas',
                names='store_id',
                title="Distribución de Ventas por Sucursal",
                template=PLOT_TEMPLATE,
                color_discrete_sequence=COLOR_SEQ
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                analisis_sucursales,
                x='store_id',
                y='Cantidad Órdenes',
                title="Cantidad de Órdenes por Sucursal",
                template=PLOT_TEMPLATE,
                color='store_id',
                color_discrete_sequence=COLOR_SEQ
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Tabla de análisis de sucursales
        st.subheader("📋 Resumen por Sucursal")
        st.dataframe(analisis_sucursales, width='stretch')
    
    # Análisis de tipos de pago
    st.subheader("💳 Análisis por Tipo de Pago")
    if 'payment_type' in sales_data.columns:
        analisis_pagos = sales_data.groupby('payment_type').agg({
            'total_amount': ['sum', 'count', 'mean']
        }).round(2)
        analisis_pagos.columns = ['Total Ventas', 'Cantidad Órdenes', 'Valor Promedio']
        analisis_pagos = analisis_pagos.reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                analisis_pagos,
                x='payment_type',
                y='Total Ventas',
                title="Ventas por Tipo de Pago",
                template=PLOT_TEMPLATE,
                color='payment_type',
                color_discrete_sequence=COLOR_SEQ
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(analisis_pagos, use_container_width=True)
    
    # Análisis por día de la semana
    st.subheader("📅 Análisis por Día de la Semana")
    if 'dia_semana' in sales_data.columns:
        analisis_dias = sales_data.groupby('dia_semana').agg({
            'total_amount': ['sum', 'count', 'mean']
        }).round(2)
        analisis_dias.columns = ['Total Ventas', 'Cantidad Órdenes', 'Valor Promedio']
        analisis_dias = analisis_dias.reset_index()
        
        # Ordenar por día de la semana
        dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        analisis_dias['dia_orden'] = analisis_dias['dia_semana'].map({dia: i for i, dia in enumerate(dias_orden)})
        analisis_dias = analisis_dias.sort_values('dia_orden')
        
        fig = px.bar(
            analisis_dias,
            x='dia_semana',
            y='Total Ventas',
            title="Ventas por Día de la Semana",
            template=PLOT_TEMPLATE,
            color='dia_semana',
            color_discrete_sequence=COLOR_SEQ
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Análisis estadístico
    st.subheader("📊 Análisis Estadístico")
    
    # Estadísticas descriptivas
    st.subheader("📈 Estadísticas Descriptivas")
    stats = get_data_statistics(sales_data)
    
    if stats:
        # Crear DataFrame de estadísticas
        stats_df = pd.DataFrame(stats).T
        stats_df = stats_df.round(2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(stats_df, use_container_width=True)
        
        with col2:
            # Resumen de calidad de datos
            st.subheader("🔍 Calidad de Datos")
            total_registros = len(sales_data)
            columnas_numericas = sales_data.select_dtypes(include=[np.number]).columns
            
            info_calidad = {
                'Total de Registros': total_registros,
                'Columnas Numéricas': len(columnas_numericas),
                'Registros Completos': sales_data.dropna().shape[0],
                'Porcentaje de Datos Completos': f"{(sales_data.dropna().shape[0] / total_registros * 100):.1f}%"
            }
            
            for key, value in info_calidad.items():
                st.metric(key, value)
    
    # Tabla de datos
    st.subheader("📋 Datos de Ventas Recientes")
    
    # Mostrar tabla de datos
    columnas_display = ['sale_id', 'sale_datetime', 'store_id', 'payment_type', 'total_amount', 'items_count']
    columnas_disponibles = [col for col in columnas_display if col in sales_data.columns]
    
    st.dataframe(
        sales_data[columnas_disponibles].head(100),
        use_container_width=True
    )
    
    # Sección de exportación
    st.markdown("---")
    st.subheader("📤 Exportar Datos")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Exportar Datos de Ventas"):
            st.markdown(create_download_link(sales_data, "ventas_dinamicas.csv"), unsafe_allow_html=True)
    
    with col2:
        if st.button("📈 Exportar Análisis Sucursales"):
            if 'store_id' in sales_data.columns:
                analisis_sucursales = sales_data.groupby('store_id').agg({
                    'total_amount': ['sum', 'count', 'mean']
                }).round(2)
                analisis_sucursales.columns = ['Total Ventas', 'Cantidad Órdenes', 'Valor Promedio']
                analisis_sucursales = analisis_sucursales.reset_index()
                st.markdown(create_download_link(analisis_sucursales, "analisis_sucursales_dinamico.csv"), unsafe_allow_html=True)
    
    with col3:
        if st.button("💳 Exportar Análisis Pagos"):
            if 'payment_type' in sales_data.columns:
                analisis_pagos = sales_data.groupby('payment_type').agg({
                    'total_amount': ['sum', 'count', 'mean']
                }).round(2)
                analisis_pagos.columns = ['Total Ventas', 'Cantidad Órdenes', 'Valor Promedio']
                analisis_pagos = analisis_pagos.reset_index()
                st.markdown(create_download_link(analisis_pagos, "analisis_pagos_dinamico.csv"), unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    with st.expander("ℹ️ Cómo leer este dashboard"):
        st.write("""
        - Las métricas muestran el agregado del rango filtrado.
        - El gráfico por hora apila por sucursal para comparar rápidamente qué tienda vende más por franja horaria.
        - Usa la barra lateral para filtrar por fechas, tienda y tipo de pago.
        - Activa el auto-refresh para ver datos en vivo cada 5s.
        """)
    st.markdown("**Dashboard ERP - Datos Dinámicos** · Streamlit + MongoDB")
    
    # Auto-refresh cada 5 segundos
    if st.sidebar.checkbox("🔄 Auto-actualizar cada 5 segundos"):
        st.sidebar.info("Los datos se actualizarán automáticamente cada 5 segundos")
        import time
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    main()
