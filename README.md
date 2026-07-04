# ShoppingBuddy 🛍️

A modern, high-performance, and secure e-commerce platform built with Django, Tailwind CSS, and Alpine.js.

## 🌟 Overview
ShoppingBuddy provides a seamless, premium shopping experience. By combining Django's robust backend architecture with a blazing-fast, utility-first frontend, we deliver a scalable application ready for production environments.

## 📸 Screenshots
*(Insert placeholders here)*
- ![Homepage](/docs/assets/home.png)
- ![Product Detail](/docs/assets/detail.png)
- ![Cart Flow](/docs/assets/cart.png)

## ✨ Features
- **Modern UI/UX**: Fully responsive, accessible, and fast interface built with Tailwind CSS & Alpine.js.
- **Robust Catalog**: Categorized product listings with scalable pagination and dynamic search.
- **Session-Based Cart**: Persistent shopping cart seamlessly managed via secure cookies and sessions.
- **Secure Authentication**: Hardened login/registration flows guarding against Open Redirects and CSRF attacks.
- **Admin Dashboard**: Professional, optimized back-office for store owners with intuitive inline-editing and metrics.

## 🛠️ Tech Stack
- **Backend**: Django 5.x, Python 3.10+
- **Frontend**: HTML5, Tailwind CSS (Standalone CLI), Alpine.js, Lucide Icons
- **Database**: SQLite (Dev) / PostgreSQL (Production)

## 📁 Folder Structure
```
shoppingbuddy/
├── accounts/          # User authentication and registration
├── cart/              # Cart session management and context processors
├── shop/              # Product catalog, categories, and core views
├── shoppingbuddy/     # Core project settings and WSGI/ASGI configs
├── static/            # Compiled Tailwind CSS and Alpine/Lucide assets
├── templates/         # Modular Django templates & components
└── docs/              # Architecture, security, and deployment documentation
```

## 🚀 Installation & Running Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/shoppingbuddy.git
   cd shoppingbuddy
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-super-secret-key
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   ```

5. **Run Migrations & Start Server:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## 🏭 Production Deployment
For production, refer to [DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 🗺️ Future Roadmap
- Complete the Checkout & Payment Gateway Integration (Stripe).
- Migrate to a Custom `AbstractUser` model.
- Implement Celery for background email tasks.
- Add robust Rate Limiting via Redis.

## 📄 License
This project is licensed under the MIT License.
