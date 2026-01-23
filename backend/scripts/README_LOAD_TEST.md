# 🚀 Load Testing - Guía de Uso

## 📝 Descripción

Script para generar N cantidad de peticiones de prueba concurrentes contra la API de aplicaciones de crédito.

## 🔧 Instalación de Dependencias

```bash
# Instalar httpx (cliente HTTP asíncrono)
pip install httpx
```

## 📖 Uso Básico

### 1. Test Simple (10 peticiones, 5 concurrentes)

```bash
cd backend
python scripts/load_test.py --requests 10 --concurrent 5
```

### 2. Test Moderado (100 peticiones, 10 concurrentes)

```bash
python scripts/load_test.py --requests 100 --concurrent 10
```

### 3. Test de Carga Alta (1000 peticiones, 50 concurrentes)

```bash
python scripts/load_test.py --requests 1000 --concurrent 50 --delay 0.1
```

### 4. Test con Autenticación JWT

```bash
# Primero obtén un token válido
export JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

python scripts/load_test.py \
  --requests 100 \
  --concurrent 10 \
  --token "$JWT_TOKEN"
```

### 5. Test para País Específico (Solo España)

```bash
python scripts/load_test.py \
  --requests 50 \
  --country ES \
  --concurrent 10
```

### 6. Test contra Servidor Remoto

```bash
python scripts/load_test.py \
  --requests 100 \
  --url "https://api.production.com/api/v1" \
  --token "$JWT_TOKEN"
```

## 🎯 Parámetros Disponibles

| Parámetro | Descripción | Default | Ejemplo |
|-----------|-------------|---------|---------|
| `-r, --requests` | Número total de peticiones | 10 | `--requests 100` |
| `-c, --concurrent` | Peticiones concurrentes por batch | 10 | `--concurrent 20` |
| `-u, --url` | URL base de la API | `http://localhost:8000/api/v1` | `--url https://api.prod.com/api/v1` |
| `-t, --token` | JWT token para autenticación | None | `--token "eyJ..."` |
| `--country` | País específico (ES, MX, BR, CO, IT, PT) | Aleatorio | `--country MX` |
| `-d, --delay` | Delay entre batches (segundos) | 0.5 | `--delay 1.0` |
| `--no-idempotency` | No incluir idempotency_key | False | `--no-idempotency` |

## 📊 Output Ejemplo

```
================================================================================
🔧 CONFIGURACIÓN DEL LOAD TEST
================================================================================
📊 Total de peticiones: 100
⚡ Concurrencia por batch: 10
🌐 URL: http://localhost:8000/api/v1
🌍 País: Aleatorio
⏱️  Delay entre batches: 0.5s
🔑 Idempotency: Sí
🔐 Autenticación: No
================================================================================

📦 Se ejecutarán 10 batches

🚀 Batch #1: Enviando 10 peticiones concurrentes...
✅ Request #1: SUCCESS - ID: a1b2c3d4-... - 0.15s
✅ Request #2: SUCCESS - ID: e5f6g7h8-... - 0.18s
...

================================================================================
📊 ESTADÍSTICAS DEL LOAD TEST
================================================================================

⏱️  Duración Total: 12.45 segundos
📝 Total Peticiones: 100
✅ Exitosas: 98 (98.0%)
❌ Fallidas: 2 (2.0%)

⚡ Tiempos de Respuesta:
   • Promedio: 0.156s
   • Mínimo: 0.089s
   • Máximo: 0.312s
   • Throughput: 8.03 req/s

📋 Códigos de Estado:
   • 201: 98 peticiones
   • 400: 2 peticiones

💾 Resultados guardados en: load_test_results_20260123_093000.json
```

## 🧪 Casos de Uso Comunes

### Prueba de Estrés Gradual

```bash
# Empezar con carga baja
python scripts/load_test.py --requests 50 --concurrent 5

# Incrementar gradualmente
python scripts/load_test.py --requests 100 --concurrent 10
python scripts/load_test.py --requests 200 --concurrent 20
python scripts/load_test.py --requests 500 --concurrent 50
```

### Test de Diferentes Países

```bash
# Test por país
for country in ES MX BR CO IT PT; do
  echo "Testing $country..."
  python scripts/load_test.py --requests 20 --country $country
done
```

### Test Sin Rate Limiting (máxima velocidad)

```bash
python scripts/load_test.py \
  --requests 1000 \
  --concurrent 100 \
  --delay 0
```

## 📈 Datos de Prueba Generados

El script genera automáticamente datos válidos para cada país:

### España (ES)
- **Documento**: DNI válido (8 dígitos + letra)
- **Moneda**: EUR
- **Montos**: €5,000 - €30,000
- **Ingresos**: €2,000 - €8,000

### México (MX)
- **Documento**: CURP válido
- **Moneda**: MXN
- **Montos**: $20,000 - $200,000 MXN
- **Ingresos**: $10,000 - $50,000 MXN

### Brasil (BR)
- **Documento**: CPF válido
- **Moneda**: BRL
- **Montos**: R$10,000 - R$100,000
- **Ingresos**: R$5,000 - R$30,000

### Colombia (CO)
- **Documento**: Cédula
- **Moneda**: COP
- **Montos**: $5M - $50M COP
- **Ingresos**: $3M - $15M COP

### Italia (IT) / Portugal (PT)
- **Moneda**: EUR
- **Montos**: €5,000 - €40,000
- **Ingresos**: €2,000 - €10,000

## 🔍 Análisis de Resultados

Los resultados se guardan en `load_test_results_YYYYMMDD_HHMMSS.json`:

```json
{
  "total": 100,
  "success": 98,
  "failed": 2,
  "status_codes": {
    "201": 98,
    "400": 2
  },
  "response_times": [0.156, 0.189, ...],
  "errors": {
    "HTTP_400": 2
  }
}
```

## ⚠️ Consideraciones

1. **Rate Limiting**: Si tienes rate limiting habilitado, ajusta `--delay` para evitar ser bloqueado
2. **JWT Token**: Para rate limiting por usuario, usa `--token` con un token válido
3. **Base de Datos**: Las peticiones crean registros reales en la base de datos
4. **Workers**: Asegúrate de tener workers ARQ corriendo para procesar las aplicaciones
5. **Unicidad**: Cada petición genera documentos únicos con timestamp para evitar duplicados

## 🛠️ Troubleshooting

### Error: "Connection refused"
```bash
# Verifica que el backend esté corriendo
docker-compose ps
# O si corres local:
ps aux | grep uvicorn
```

### Error: "401 Unauthorized"
```bash
# Necesitas un JWT token válido
# Obtén uno del endpoint /auth/login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

### Error: "Too Many Requests (429)"
```bash
# Reduce la concurrencia o aumenta el delay
python scripts/load_test.py --requests 100 --concurrent 5 --delay 1.0
```

## 📚 Referencias

- [httpx Documentation](https://www.python-httpx.org/)
- [API Documentation](../README.md)
- [Authentication Guide](../docs/authentication.md)
