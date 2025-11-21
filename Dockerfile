# Utiliser une image Python officielle légère
FROM python:3.11-slim

# Définir les variables d'environnement
# PYTHONDONTWRITEBYTECODE: Empêche Python d'écrire des fichiers .pyc
# PYTHONUNBUFFERED: Assure que les logs sont affichés immédiatement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires
# gettext: requis pour la compilation des traductions (msgfmt)
RUN apt-get update && apt-get install -y \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier des dépendances
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le projet
COPY . /app/

# Copier et rendre exécutable le script d'entrée
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Collecter les fichiers statiques
# On utilise un dummy secret key juste pour cette étape de build
# Note: collectstatic est aussi lancé dans entrypoint.sh pour gérer les volumes montés,
# mais on le garde ici pour l'image de base.
# On définit SECRET_KEY temporairement pour que collectstatic fonctionne
RUN SECRET_KEY=dummy-key-for-build python manage.py collectstatic --noinput --clear

# Compiler les fichiers de traduction (.po -> .mo)
RUN python manage.py compilemessages

# Exposer le port 8000 (Gunicorn)
EXPOSE 8000

# Définir le point d'entrée
ENTRYPOINT ["/app/entrypoint.sh"]
