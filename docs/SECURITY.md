# 🔒 Security Policy

## Supported Versions
Only the `main` branch is actively supported with security updates.

## Reporting a Vulnerability
If you discover a security vulnerability, please DO NOT open a public issue. Email the repository owner directly.

## Implemented Security Measures
This project implements strict security controls conforming to OWASP guidelines:
1. **CSRF Protection**: Native Django middleware with strictly bound `CSRF_TRUSTED_ORIGINS`.
2. **Secure Cookies**: Both Session and CSRF cookies are strictly `HttpOnly` and `Secure`.
3. **HSTS Enforcement**: HTTPS is strictly enforced via `SECURE_HSTS_PRELOAD` and `SECURE_HSTS_SECONDS`.
4. **Open Redirect Mitigation**: Form `next` parameters are aggressively sanitized via `url_has_allowed_host_and_scheme`.
5. **ORM Safety**: Parameterized queries are used natively by the Django ORM to prevent SQL Injection.
6. **Authentication Guarding**: Logged-in users are explicitly blocked from accessing auth endpoints to prevent state confusion attacks.
