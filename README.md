# CineVerse — Subscription & Billing Automation Platform

A full-stack web application for managing subscription plans, customer accounts, billing cycles, payments, invoices, refunds, and administrative analytics.

CineVerse combines a **React frontend** with a **FastAPI backend** to demonstrate how a subscription-based platform can organize billing workflows, automate recurring tasks, and provide clear visibility into customer and financial activity.

## ✨ Key Features

- **Subscription Management** — Manage plans, subscriptions, billing cycles, and subscription lifecycle operations.
- **Billing Automation** — Support recurring billing workflows and scheduled tasks using Celery and Redis.
- **Payment Processing** — Simulate payment gateway operations and handle payment status updates through webhook workflows.
- **Invoice Management** — Generate invoices, download PDF invoices, and access invoice payment and refund details.
- **Refund Processing** — Support full and partial refunds with corresponding billing records.
- **Tax and Proration** — Calculate applicable taxes and handle prorated charges during eligible subscription plan changes.
- **Authentication and Authorization** — JWT-based authentication, role-based administrative access, and customer ownership enforcement.
- **Analytics Dashboard** — Monitor revenue, customers, subscriptions, payments, and refunds using aggregated backend data.
- **Reports and Exports** — Generate administrative reports in CSV, Excel, and PDF formats.
- **Audit Trail and Notifications** — Track account activity and support asynchronous email notifications.

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy |
| Database migrations | Alembic |
| Background processing | Celery, Celery Beat |
| Message broker and caching | Redis |
| API documentation | Swagger UI, OpenAPI |
| Testing | Pytest |
| Containerization | Docker, Docker Compose |

## 🏗️ Architecture

```text
┌─────────────────────────────┐
│      React Frontend         │
│ Customer & Admin Interfaces │
└──────────────┬──────────────┘
               │ REST API
               ▼
┌─────────────────────────────┐
│       FastAPI Backend       │
│ Authentication & API Routes │
├─────────────────────────────┤
│      Service Layer          │
│ Billing, Payments, Reports  │
├─────────────────────────────┤
│     Repository Layer        │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│         PostgreSQL          │
└─────────────────────────────┘

 Celery Worker + Celery Beat
               │
               ▼
             Redis
```

## 📁 Project Structure

```text
CineVerse/
├── cineverse-backend/     # API, business logic, database, tasks and tests
└── cineverse-frontend/    # React application and user interfaces
```

## 🚀 Getting Started

### Prerequisites

- Python and pip
- Node.js and npm
- Docker Desktop and Docker Compose
- Git

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/CineVerse.git
cd CineVerse
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Configure the backend

```bash
cd cineverse-backend
```

Create your local environment configuration from the provided template:

```bash
# Windows PowerShell
Copy-Item .env.example .env
```

Review `.env` and configure the database, application secret, Redis, and other required settings. Never commit your real `.env` file.

### 3. Start the backend services

From the backend directory:

```bash
docker compose up --build
```

When the services are ready, the API documentation should be available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 4. Start the frontend

Open a separate terminal:

```bash
cd cineverse-frontend
npm install
npm run dev
```

Configure the frontend API base URL using its documented environment variables and the address of the running backend. Use the URL printed by Vite to open the frontend.

## 🧪 Testing

The backend includes a Pytest suite covering authentication, subscription lifecycle operations, billing logic, payments, refunds, analytics, and API authorization.

Run the tests using the project's documented test database configuration:

```bash
cd cineverse-backend
pytest tests/ -v
```

Use a dedicated test database and test-only credentials. Configure the test environment before running tests; do not run destructive tests against production data.

## 🔐 Security Notes

- Never commit `.env` files, API keys, database passwords, JWT secrets, or webhook secrets.
- Keep real credentials out of source code and documentation.
- Use strong secrets and HTTPS for deployed environments.
- Payment processing in the documented mock gateway simulates gateway behavior; it is not a substitute for a production payment provider integration.

## 🎯 Project Objective

CineVerse demonstrates full-stack development practices through the integration of REST APIs, database modeling, authentication, subscription lifecycle management, automated billing tasks, financial workflows, reporting, and administrative interfaces.

## 📚 Documentation

- [Backend Documentation](cineverse-backend/README.md)
- [Frontend Documentation](cineverse-frontend/README.md)

## ⚠️ Project Status

This repository is intended as a software development project and demonstration of subscription and billing workflows. Review the configuration, deployment requirements, and payment integration before using it in a production environment.
