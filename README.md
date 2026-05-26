# Expense Tracker

A professional, user-friendly Django web application to help users manage personal finances. The project provides tools for recording income and expenses, viewing analytics, and maintaining user profiles with savings and income details.


# Demo video:   https://www.youtube.com/watch?v=I2P80HcR73Q

## Features

- Register, log in, and manage a personal finance dashboard
- Add, edit, and delete income and expense records
- Search, filter, and paginate transaction records
- Weekly, monthly, and yearly summaries and analytics
- Category-based expense grouping and simple budget alerts
- User profile with basic savings and income tracking
- Responsive templates with multiple layouts

## Technology Stack

- Python 3.10+ (recommended)
- Django (tested with the project's Django version)
- SQLite (default development database)
- HTML, CSS, and JavaScript for front-end templates

## Project Structure

- `ExpenseTracker/` — Django project settings and configuration
- `home/` — Main application: models, views, forms, templates
- `templates/` — HTML templates used by the app
- `static/` — CSS, JavaScript, and image assets
- `manage.py` — Django project management script
- `db.sqlite3` — Development SQLite database (auto-generated)

## Prerequisites

- Python 3.10 or newer
- pip
- A virtual environment tool such as `venv` or `virtualenv`

## Setup & Installation

1. Clone the repository:

	git clone <repository-url>
	cd ExpenseTracker

2. Create and activate a virtual environment:

	python -m venv venv
	# Windows
	venv\Scripts\activate
	# macOS / Linux
	source venv/bin/activate

3. Install dependencies:

	pip install -r requirements.txt

	If `requirements.txt` is not present, install Django and other dependencies manually, for example:

	pip install django

4. Apply database migrations:

	python manage.py migrate

5. (Optional) Create a superuser to access the admin interface:

	python manage.py createsuperuser

6. Run the development server:

	python manage.py runserver

7. Open your browser at `http://127.0.0.1:8000/` to view the site.

## Running Tests

Run the project's test suite with:

```
python manage.py test
```

## Static Files & Production Notes

- When deploying to production, set `DEBUG = False` and configure `ALLOWED_HOSTS` in `ExpenseTracker/settings.py`.
- Collect static files before deploying:

```
python manage.py collectstatic
```

- Configure a proper production database (PostgreSQL, MySQL, etc.), use a WSGI server (Gunicorn, uWSGI), and serve static files via a CDN or web server (NGINX) or use WhiteNoise for simplified static serving.

## Contributing

Contributions are welcome. Typical workflow:

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests where appropriate
4. Open a pull request describing your changes

Please follow existing code style and be sure tests pass before submitting a PR.

## Troubleshooting

- If migrations fail, try removing `db.sqlite3` and re-running `python manage.py migrate` (note: this deletes local data).
- If static files are missing in production, confirm `collectstatic` has been run and review static file settings.

## Roadmap / Future Enhancements

- Interactive graphical analytics (charts)
- Export transactions to CSV/PDF
- Email notifications for budget thresholds
- Mobile-first responsive improvements

## Credits

Built with Django and contributions from the open source community.

## Author

Angothu Adhisheshu

---
If you have questions or need help running the project locally, open an issue or contact the author.
