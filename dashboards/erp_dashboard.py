# erp_dashboard.py
# Dashboard estático para datos procesados del sistema ERP

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pymongo
import io, base64
from datetime import datetime
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.config import MONGODB_CONNECTION_STRING, MONGODB_DATABASE, COLLECTIONS

# ===== Config =====
MONGO_URI = MONGODB_CONNECTION_STRING
DB_NAME = MONGODB_DATABASE

st.set_page_config(page_title="Dashboard ERP", page_icon="📊", layout="wide")

# ---------- Helpers ----------
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

@st.cache_data(ttl=300)
def load_processed_data():
    """Carga datos procesados/estáticos"""
    db = get_mongo_data()
    if db is None:
        return pd.DataFrame()
    
    # Cargar datos de resumen diario
    data = list(db.daily_sales_summary.find())
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Limpiar y convertir datos
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        df['month_name'] = df['date'].dt.strftime('%B')
        df['quarter'] = df['date'].dt.quarter
    
    # Convertir columnas numéricas
    numeric_columns = ['total_sales', 'total_orders', 'avg_order_value', 'total_customers', 'total_items']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

@st.cache_data(ttl=300)
def load_store_analysis():
    """Carga análisis de tiendas"""
    db = get_mongo_data()
    if db is None:
        return pd.DataFrame()
    
    data = list(db.store_analysis.find())
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Convertir columnas numéricas
    numeric_columns = ['total_sales', 'total_orders', 'avg_order_value', 'total_items', 'unique_customers']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

@st.cache_data(ttl=300)
def load_monthly_sales_by_store():
    """Agrega ventas por mes y sucursal desde la colección sales (para barras apiladas)."""
    db = get_mongo_data()
    if db is None:
        return pd.DataFrame()

    pipeline = [
        {"$addFields": {"sale_date": {"$dateFromString": {"dateString": "$sale_datetime", "format": "%Y-%m-%d %H:%M:%S"}}}},
        {"$group": {
            "_id": {
                "year": {"$year": "$sale_date"},
                "month": {"$month": "$sale_date"},
                "store_id": "$store_id"
            },
            "total_sales": {"$sum": "$total_amount"}
        }},
        {"$project": {
            "year": "$_id.year",
            "month": "$_id.month",
            "store_id": "$_id.store_id",
            "total_sales": 1,
            "_id": 0
        }},
        {"$sort": {"year": 1, "month": 1, "store_id": 1}}
    ]

    try:
        data = list(db.sales.aggregate(pipeline))
    except Exception:
        data = []

    df = pd.DataFrame(data)
    if not df.empty:
        df["month_name"] = df["month"].map({1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"})
    return df

def download_link_df(df: pd.DataFrame, fname: str, kind="csv"):
    """Genera enlace de descarga para DataFrame"""
    if df.empty: 
        return ""
    if kind == "csv":
        b = df.to_csv(index=False).encode()
        mime = "text/csv"
    else:
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            df.to_excel(w, index=False)
        b = bio.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    b64 = base64.b64encode(b).decode()
    return f'<a download="{fname}" href="data:{mime};base64,{b64}">Descargar {kind.upper()}</a>'

# ---------- Main App ----------
st.title("📊 Dashboard ERP - Datos Procesados")
st.caption("Análisis de datos históricos del sistema ERP")

# Cargar datos
processed_data = load_processed_data()
store_analysis = load_store_analysis()

if processed_data.empty:
    st.warning("No hay datos procesados disponibles. Ejecuta primero el procesador de datos.")
    st.stop()

# ---------- Sidebar Filters ----------
st.sidebar.header("🔧 Filtros")

# Filtro de año
if 'year' in processed_data.columns:
    years = sorted(processed_data['year'].dropna().unique())
    selected_year = st.sidebar.selectbox("Año", ["Todos"] + years, index=0)
    if selected_year != "Todos":
        processed_data = processed_data[processed_data['year'] == selected_year]

# Filtro de mes
if 'month' in processed_data.columns:
    months = sorted(processed_data['month'].dropna().unique())
    month_names = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                  7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    month_options = ["Todos"] + [f"{month_names.get(m, m)}" for m in months]
    selected_month = st.sidebar.selectbox("Mes", month_options, index=0)
    if selected_month != "Todos":
        month_num = next(k for k, v in month_names.items() if v == selected_month)
        processed_data = processed_data[processed_data['month'] == month_num]

# ---------- KPIs ----------
st.header("📈 Métricas Principales")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_sales = processed_data['total_sales'].sum() if 'total_sales' in processed_data.columns else 0
    st.metric("💰 Ingresos Totales", f"${total_sales:,.2f}")

with col2:
    total_orders = processed_data['total_orders'].sum() if 'total_orders' in processed_data.columns else 0
    st.metric("📦 Total Órdenes", f"{total_orders:,.0f}")

with col3:
    avg_order_value = processed_data['avg_order_value'].mean() if 'avg_order_value' in processed_data.columns else 0
    st.metric("💵 Ticket Promedio", f"${avg_order_value:,.2f}")

with col4:
    total_customers = processed_data['total_customers'].sum() if 'total_customers' in processed_data.columns else 0
    st.metric("👥 Total Clientes", f"{total_customers:,.0f}")

# ---------- Gráficos ----------
st.header("📊 Análisis de Ventas")

# Evolución de ventas
if 'date' in processed_data.columns and 'total_sales' in processed_data.columns:
    fig = px.line(processed_data, x='date', y='total_sales', 
                  title='Evolución de Ventas Diarias',
                  labels={'total_sales': 'Ventas ($)', 'date': 'Fecha'})
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

# Análisis mensual (barras apiladas por sucursal)
monthly_store = load_monthly_sales_by_store()
if not monthly_store.empty:
    # filtrar por año seleccionado si aplica
    try:
        selected_year  # noqa: F401
        if 'selected_year' in locals() and selected_year != "Todos":
            monthly_store = monthly_store[monthly_store['year'] == selected_year]
    except Exception:
        pass

    # Ordenar meses de 1..12 para el eje X
    order_months = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    monthly_store['month_name'] = pd.Categorical(monthly_store['month_name'], categories=order_months, ordered=True)

    fig = px.bar(
        monthly_store,
        x='month_name', y='total_sales', color='store_id',
        title='Ventas por Mes (Apilado por Sucursal)',
        labels={'total_sales': 'Ventas ($)', 'month_name': 'Mes', 'store_id': 'Sucursal'},
        template='plotly_white'
    )
    fig.update_layout(barmode='stack', xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# Análisis trimestral
if 'quarter' in processed_data.columns and 'total_sales' in processed_data.columns:
    quarterly_data = processed_data.groupby('quarter')['total_sales'].sum().reset_index()
    quarterly_data['quarter_name'] = 'Q' + quarterly_data['quarter'].astype(str)
    
    fig = px.pie(quarterly_data, values='total_sales', names='quarter_name',
                 title='Distribución de Ventas por Trimestre')
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

# ---------- Análisis de Tiendas ----------
if not store_analysis.empty:
    st.header("🏪 Análisis por Sucursal")
    
    # Mapa de calor de ventas por sucursal
    if 'store_id' in store_analysis.columns and 'total_sales' in store_analysis.columns:
        # Asegurar que store_id sea columna 1-D de tipo string
        store_df = store_analysis.copy()
        store_df['store_id'] = store_df['store_id'].astype(str)

        # Construir matriz (filas=metricas, columnas=sucursal)
        heatmap_df = store_df[['store_id', 'total_sales', 'total_orders', 'avg_order_value']]
        heatmap_df = heatmap_df.set_index('store_id').T

        fig = px.imshow(
            heatmap_df,
            text_auto=True,
            aspect="auto",
            title="Mapa de Calor - Métricas por Sucursal",
            color_continuous_scale="RdYlBu_r"
        )
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    
    # Top sucursales
    if 'store_id' in store_analysis.columns and 'total_sales' in store_analysis.columns:
        top_stores = store_analysis.nlargest(10, 'total_sales')[['store_id', 'total_sales', 'total_orders', 'avg_order_value']]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Top 10 Sucursales por Ventas")
            st.dataframe(top_stores, use_container_width=True)
        
        with col2:
            # Gráfico de barras de top sucursales
            fig = px.bar(top_stores, x='store_id', y='total_sales',
                        title='Top 10 Sucursales por Ventas',
                        labels={'total_sales': 'Ventas ($)', 'store_id': 'Sucursal'})
            fig.update_layout(template="plotly_white", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

# ---------- Análisis Estadístico ----------
st.header("📊 Análisis Estadístico")

if not processed_data.empty:
    # Estadísticas descriptivas (se mantiene, se elimina la matriz de correlación)
    numeric_cols = processed_data.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        st.subheader("Estadísticas Descriptivas")
        desc_stats = processed_data[numeric_cols].describe().round(2)
        st.dataframe(desc_stats, use_container_width=True)

# ---------- Exportación de Datos ----------
st.header("📥 Exportación de Datos")

col1, col2, col3 = st.columns(3)

with col1:
    if not processed_data.empty:
        st.markdown(download_link_df(processed_data, "datos_procesados.csv", "csv"), unsafe_allow_html=True)

with col2:
    if not processed_data.empty:
        st.markdown(download_link_df(processed_data, "datos_procesados.xlsx", "xlsx"), unsafe_allow_html=True)

with col3:
    if not store_analysis.empty:
        st.markdown(download_link_df(store_analysis, "analisis_sucursales.csv", "csv"), unsafe_allow_html=True)

# ---------- Footer ----------
st.markdown("---")
st.caption("Dashboard ERP - Sistema de Análisis de Datos Comerciales")

if __name__ == "__main__":
    pass