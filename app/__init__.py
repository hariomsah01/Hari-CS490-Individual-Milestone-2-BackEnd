import os
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

def create_app():
    load_dotenv()
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}})

    def dsn():
        host=os.getenv("DB_HOST","127.0.0.1"); port=os.getenv("DB_PORT","3306")
        user=os.getenv("DB_USER","root"); pw=os.getenv("DB_PASSWORD",""); name=os.getenv("DB_NAME","sakila")
        return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{name}"
    engine = create_engine(dsn(), poolclass=QueuePool, pool_pre_ping=True)
    app.config["ENGINE"] = engine

    @app.get("/api/health")
    def health(): return jsonify(ok=True)

    from .routes.films import bp as films_bp
    from .routes.customers import bp as customers_bp
    from .routes.rentals import bp as rentals_bp
    from .routes.actors import bp as actors_bp 
    app.register_blueprint(films_bp, url_prefix="/api/films")
    app.register_blueprint(customers_bp, url_prefix="/api/customers")
    app.register_blueprint(rentals_bp, url_prefix="/api/rentals")
    app.register_blueprint(actors_bp, url_prefix="/api/actors")

    @app.errorhandler(Exception)
    def on_error(e):
        app.logger.exception(e)
        return jsonify(error="Internal server error"), 500
    return app
