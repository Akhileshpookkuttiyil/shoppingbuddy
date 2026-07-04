# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Complete UI/UX redesign using Tailwind CSS and Alpine.js.
- Reusable Django template components (`_navbar.html`, `_product_card.html`, `_pagination.html`).
- Global context processors for Cart Counts and Categories.
- Safe Open Redirect protections on authentication endpoints.
- Professional Django Admin configurations with thumbnails and aggregated badges.
- Built-in scalable pagination.

### Changed
- Eliminated legacy Bootstrap 3 UI dependencies.
- Replaced direct Python database loops with optimized Django ORM aggregates (`Sum`, `Count`).
- Replaced massive catalog queries with `select_related` and pagination for O(1) performance scaling.
- Hardened `settings.py` for production environments (HSTS, secure cookies, trusted origins).
