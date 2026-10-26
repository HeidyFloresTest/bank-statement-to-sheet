# 🏦 BankReconcile

[![CI/CD Pipeline](https://github.com/HeidyFloresTest/bank-statement-to-sheet/actions/workflows/ci.yml/badge.svg)](https://github.com/HeidyFloresTest/bank-statement-to-sheet/actions)
[![Python 3.10 | 3.11 | 3.12](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Coverage: >85%](https://img.shields.io/badge/Coverage->85%25-success.svg)](coverage.xml)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Type%20Checked-Mypy%20Strict-blue.svg)](http://mypy-lang.org/)

**BankReconcile** es un motor empresarial de extracción, normalización y conciliación financiera automatizada de extractos bancarios en formatos **PDF** y **CSV** (compatible con entidades globales como BBVA, Santander, Chase, Citi, etc.). Permite auditar en tiempo real cargos y abonos, recalculando métricas de flujo de caja y generando reportes corporativos en Excel (`.xlsx`) listos para auditorías contables.

---

## 🏛️ Diagrama de Arquitectura

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Cliente Web / Navegador                         │
│     (HTML5 + Tailwind CSS + Lucide Icons + Live Editable Grid)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / Streaming / Multipart
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Application Gateway                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ObservabilityMiddleware (X-Request-ID, Latency Ms, OWASP Headers)   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ JSON Structured Logger & Telemetry Aggregator (Metrics Tracker)     │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │                                        │
                ▼                                        ▼
┌───────────────────────────────┐        ┌───────────────────────────────┐
│     Extracción de Datos       │        │     Generador Corporativo     │
│ ┌───────────────────────────┐ │        │ ┌───────────────────────────┐ │
│ │ Normalizador Financiero   │ │        │ │ openpyxl Engine           │ │
│ │ (Fechas ISO, Monedas,     │ │        │ │ - Hojas de Transacciones  │ │
│ │  Formatos Miles/Decimales)│ │        │ │ - Resumen de KPIs         │ │
│ ├───────────────────────────┤ │        │ │ - Fórmulas dinámicas SUM  │ │
│ │ PDFExtractor (pdfplumber) │ │        │ │ - Paleta Navy Segoe UI    │ │
│ ├───────────────────────────┤ │        │ │ - Auto-fit de columnas    │ │
│ │ CSVExtractor (pandas/csv) │ │        │ └───────────────────────────┘ │
│ └───────────────────────────┘ │        └───────────────────────────────┘
└───────────────────────────────┘
```

---

## ✨ Características Principales

- **Procesamiento de Extractos Híbridos:**
  - **PDF Digital & Tablas:** Extracción en memoria con `pdfplumber` tanto de tablas estructuradas como de secuencias de texto digital con fallbacks regex.
  - **CSV & Tabular:** Auto-detección de delimitadores (`,`, `;`, `\t`, `|`), múltiples codificaciones (`utf-8`, `latin-1`, `cp1252`) y mapeo inteligente de cabeceras en español e inglés.
- **Normalización Financiera Robusta:**
  - Detección matemática de separadores de miles y decimales (`1,234.50` vs `1.234,50`).
  - Reconocimiento de notación contable entre paréntesis (`(500.00)` como egreso) y signos explícitos (`+` / `-`).
  - Estandarización de fechas a ISO 8601 (`YYYY-MM-DD`).
- **Generación de Excel de Nivel Corporativo:**
  - Fórmulas de suma dinámica en vivo (`=SUM(...)`).
  - Tipado numérico y monetario real (`$#,##0.00`).
  - Tipografía ejecutiva *Segoe UI*, zebra striping y hoja de resumen ejecutivo.
- **Frontend Interactivo Single-File:**
  - Zona Drag & Drop con cola de archivos y eliminación individual.
  - Tarjetas KPI en vivo (Total Ingresos, Total Egresos, Saldo Neto y Conteo).
  - Tabla interactiva con celdas editables en vivo y recálculo automático de KPIs antes de descargar.
- **Seguridad y Observabilidad Enterprise:**
  - Middleware de correlación (`X-Request-ID`) y tiempos de respuesta (`X-Response-Time-Ms`).
  - Cabeceras de seguridad OWASP (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`).
  - Logs estructurados en JSON y endpoints de telemetría `/health` y `/api/metrics`.

---

## 🚀 Inicio Rápido

### Opción 1: Con Docker Compose (Recomendado)

Inicia el entorno completo de producción con un único comando:

```bash
docker compose up --build
```

La aplicación estará disponible inmediatamente en: [http://localhost:8000](http://localhost:8000).

---

### Opción 2: Instalación Local con Python

#### 1. Requisitos Previos
- Python 3.10 o superior (recomendado 3.12).
- Gestor de paquetes `pip` y entorno virtual `venv`.

#### 2. Clonar el Repositorio y Configurar Entorno
```bash
git clone https://github.com/HeidyFloresTest/bank-statement-to-sheet.git
cd bank-statement-to-sheet

# Crear y activar entorno virtual
python -m venv .venv

# En Windows PowerShell:
.venv\Scripts\Activate.ps1

# En Linux / macOS:
source .venv/bin/activate
```

#### 3. Instalar Dependencias
```bash
pip install -r requirements-dev.txt
```

#### 4. Ejecutar el Servidor de Desarrollo
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Pruebas Automáticas y Calidad de Código

El repositorio cuenta con una suite completa de más de 60 pruebas unitarias e integración con cobertura superior al 85%.

### Ejecutar Pruebas con Reporte de Cobertura
```bash
pytest
```

### Ejecutar Linter y Verificación de Estilo (Ruff)
```bash
ruff check .
ruff format --check .
```

### Verificación de Tipado Estricto (Mypy)
```bash
mypy app
```

---

## 📡 Referencia de la API REST

| Método | Endpoint | Descripción | Parámetros / Payload |
|---|---|---|---|
| `GET` | `/` | Interfaz web de usuario (SPA). | - |
| `GET` | `/health` | Chequeo de estado y uptime del servicio. | - |
| `GET` | `/api/metrics` | Métricas de telemetría (requests, transacciones procesadas, errores). | - |
| `POST` | `/api/extract` | Extrae y normaliza transacciones desde archivos PDF/CSV en memoria. | `multipart/form-data`: `files` (uno o varios archivos, máx. 25MB) |
| `POST` | `/api/export` | Genera y descarga el Excel corporativo (`.xlsx`). | `application/json`: `{ transacciones: [...], nombre_reporte: str }` |

Documentación interactiva Swagger UI disponible en: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 📁 Estructura del Proyecto

```text
├── .devcontainer/              # Configuración para desarrollo en contenedores / VS Code
│   └── devcontainer.json
├── .github/
│   └── workflows/
│       └── ci.yml              # Pipeline de CI/CD (Ruff, Mypy, Pytest en Python 3.10, 3.11, 3.12)
├── app/
│   ├── excel/                  # Generador de reportes corporativos en Excel
│   │   ├── __init__.py
│   │   └── generator.py
│   ├── extractor/              # Motores de extracción y normalización
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── csv_extractor.py
│   │   ├── normalizer.py
│   │   ├── pdf_extractor.py
│   │   └── service.py
│   ├── static/                 # Frontend Single-Page Application (HTML5, Tailwind, JS)
│   │   └── index.html
│   ├── __init__.py
│   ├── config.py               # Configuración con Pydantic Settings
│   ├── main.py                 # FastAPI Gateway y endpoints REST
│   ├── observability.py        # Logging JSON, middleware y métricas
│   └── schemas.py              # Modelos Pydantic v2
├── tests/                      # Suite de pruebas Pytest (>85% cobertura)
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_excel_generator.py
│   ├── test_extractor.py
│   ├── test_observability.py
│   └── test_schemas.py
├── .env.example                # Variables de entorno documentadas
├── .gitignore                  # Exclusiones de Git
├── Dockerfile                  # Imagen Docker multi-stage optimizada
├── docker-compose.yml          # Orquestación local de contenedores
├── LICENSE                     # Licencia MIT
├── pyproject.toml              # Configuración de Pytest, Ruff, Mypy y Cobertura
├── requirements.txt            # Dependencias de producción
├── requirements-dev.txt        # Dependencias de desarrollo
└── requirements.lock           # Versiones fijadas de dependencias
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
