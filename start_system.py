# start_system.py
# Script de inicio rápido para el sistema ERP
import subprocess
import time
import sys
import os
from pathlib import Path

def run_command(command, description, wait=True):
    """Ejecuta un comando y muestra el resultado"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Comando: {command}")
    
    try:
        if wait:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            print("✅ Comando ejecutado exitosamente")
            if result.stdout:
                print(f"Salida: {result.stdout}")
        else:
            # Para comandos que no necesitan esperar
            subprocess.Popen(command, shell=True)
            print("✅ Comando iniciado en segundo plano")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando comando: {e}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def check_docker():
    """Verifica que Docker esté corriendo"""
    print("\n🔍 Verificando Docker...")
    try:
        result = subprocess.run("docker ps", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker está corriendo")
            return True
        else:
            print("❌ Docker no está corriendo")
            return False
    except Exception as e:
        print(f"❌ Error verificando Docker: {e}")
        return False

def check_files():
    """Verifica que los archivos necesarios existan"""
    print("\n🔍 Verificando archivos del sistema...")
    
    required_files = [
        "generate_erp_csv.py",
        "erp_simulator_producer.py", 
        "erp_kafka_to_mongo.py",
        "mongo_data_processor_completo.py",
        "erp_dashboard.py",
        "erp_dashboard_dinamico.py",
        "config.py",
        "docker-compose.yml"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Archivos faltantes: {missing_files}")
        return False
    else:
        print("✅ Todos los archivos necesarios están presentes")
        return True

def main():
    print("🏢 SISTEMA ERP DE BIG DATA - INICIO RÁPIDO")
    print("=" * 60)
    
    # Verificar prerrequisitos
    if not check_docker():
        print("\n❌ Docker no está corriendo. Por favor inicia Docker Desktop.")
        return
    
    if not check_files():
        print("\n❌ Faltan archivos del sistema. Verifica la instalación.")
        return
    
    print("\n✅ Prerrequisitos verificados correctamente")
    
    # Menú de opciones
    while True:
        print("\n" + "="*60)
        print("📋 MENÚ DE OPCIONES")
        print("="*60)
        print("1. 🐳 Iniciar servicios Docker (Kafka, MongoDB, etc.)")
        print("2. 📊 Procesar datos reales del CSV Superstore")
        print("3. 🔄 Ejecutar pipeline completo (Productor + Consumidor + Procesador)")
        print("4. 📈 Iniciar dashboards")
        print("5. 🔍 Verificar estado del sistema")
        print("6. 🛑 Detener servicios Docker")
        print("7. ❌ Salir")
        print("="*60)
        
        choice = input("\nSelecciona una opción (1-7): ").strip()
        
        if choice == "1":
            print("\n🐳 Iniciando servicios Docker...")
            run_command("docker-compose up -d", "Iniciando servicios Docker")
            print("\n⏳ Esperando 30 segundos para que los servicios se inicialicen...")
            time.sleep(30)
            
        elif choice == "2":
            print("\n📊 Procesando datos reales del CSV Superstore...")
            run_command("python process_superstore_csv.py", "Procesando archivos CSV desde datos reales")
            
        elif choice == "3":
            print("\n🔄 Ejecutando pipeline completo...")
            print("⚠️  IMPORTANTE: Ejecuta cada comando en una terminal separada")
            print("\nTerminal 1 - Productor Kafka:")
            print("python erp_simulator_producer.py")
            print("\nTerminal 2 - Consumidor Kafka:")
            print("python erp_kafka_to_mongo.py")
            print("\nTerminal 3 - Procesador de datos:")
            print("python mongo_data_processor_completo.py")
            
        elif choice == "4":
            print("\n📈 Iniciando dashboards...")
            print("⚠️  IMPORTANTE: Ejecuta cada comando en una terminal separada")
            print("\nTerminal 1 - Dashboard Estático (Puerto 8501):")
            print("streamlit run erp_dashboard.py --server.port 8501")
            print("\nTerminal 2 - Dashboard Dinámico (Puerto 8502):")
            print("streamlit run erp_dashboard_dinamico.py --server.port 8502")
            
        elif choice == "5":
            print("\n🔍 Verificando estado del sistema...")
            run_command("docker ps", "Estado de contenedores Docker")
            run_command("docker-compose ps", "Estado de servicios")
            
        elif choice == "6":
            print("\n🛑 Deteniendo servicios Docker...")
            run_command("docker-compose down", "Deteniendo servicios Docker")
            
        elif choice == "7":
            print("\n👋 ¡Hasta luego!")
            break
            
        else:
            print("\n❌ Opción inválida. Por favor selecciona 1-7.")

if __name__ == "__main__":
    main()
