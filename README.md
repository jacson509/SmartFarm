# SmartFarm

SmartFarm est une application Web scolaire pour surveiller les conditions environnementales des bâtiments et des espaces d’élevage. Elle gère les bâtiments, espaces, capteurs, mesures, actionneurs et commandes simulées. Elle ne gère pas les animaux individuellement.

## Objectifs

- Regrouper les bâtiments, espaces et capteurs d’une ferme.
- Consulter l’historique des températures et de l’humidité.
- Vérifier les mesures par rapport aux limites techniques et aux seuils configurés.
- Enregistrer des commandes ON/OFF simulées pour les actionneurs.
- Visualiser les données dans un dashboard et générer des mesures de démonstration.

## Technologies

Python 3.12.7, Django 5.2.19, Django REST Framework 3.16.1, SQLite, HTML5, CSS3 et JavaScript sans framework. L’environnement virtuel existant utilise le chemin `.venv\bin`.

## Architecture des applications

| Application | Responsabilité |
| --- | --- |
| `accounts` | Connexion Django, émission et révocation de token, profil API. |
| `facilities` | Bâtiments et espaces. |
| `sensors` | Capteurs, mesures, validation, filtres et historique. |
| `actuators` | Actionneurs et journal des commandes simulées. |
| `dashboard` | Résumé et données de lecture pour le dashboard et son API. |
| `simulator` | Interface et tâche locale qui envoie les mesures par l’API. |

Les mesures et commandes ne sont pas supprimables par leur API. Les relations historiques utilisent `PROTECT`; les entités liées sont archivées/désactivées quand une suppression est demandée. L’application d’alertes de la proposition initiale n’est pas développée.

## Lancement dans l’environnement actuel

Depuis le dossier SmartFarm, dans PowerShell :

```powershell
.\.venv\bin\Activate.ps1
python manage.py check
python manage.py migrate
python manage.py runserver
```

Ouvrez <http://127.0.0.1:8000/>. Le projet utilise la base SQLite existante `db.sqlite3`; ne la supprimez pas pour démarrer l’application. Si PowerShell bloque l’activation de l’environnement, l’autorisation temporaire peut être appliquée pour la session courante :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\bin\Activate.ps1
```

Pour créer un compte administrateur local :

```powershell
python manage.py createsuperuser
```

La configuration locale accepte `DJANGO_SECRET_KEY` et `DJANGO_DEBUG`. Le simulateur utilise par défaut `http://127.0.0.1:8000`; pour un autre port, définissez `SMARTFARM_API_BASE_URL`, par exemple :

```powershell
$env:SMARTFARM_API_BASE_URL = "http://127.0.0.1:8001"
```

## Interface Web

La page d’accueil `/` est le dashboard authentifié. La navigation donne accès aux bâtiments, espaces, capteurs, mesures, actionneurs et commandes.

- Bâtiments : `/buildings/`
- Espaces : `/spaces/`
- Capteurs : `/sensors/`
- Mesures : `/measurements/`
- Actionneurs : `/actuators/`
- Historique de toutes les commandes : `/commands/`
- Simulateur : `/simulator/`
- Administration Django : `/admin/`

Les pages HTML qui modifient les données demandent une connexion et utilisent les formulaires protégés par CSRF. Les pages de suppression demandent une confirmation.

## Authentification API

Obtenez un token par `POST /api/v1/auth/token/` avec le JSON `{"username":"…","password":"…"}`. Envoyez-le ensuite dans `Authorization: Token <token>`. Le profil est disponible par `GET /api/v1/auth/me/` et le token présenté peut être révoqué par `POST /api/v1/auth/token/revoke/`.

Les endpoints REST répondent en JSON et exigent un token par défaut. Le simulateur Web utilise la session et CSRF pour ses boutons; le token employé ensuite pour publier des mesures reste côté serveur et n’est jamais rendu dans le HTML ou JavaScript.

## API REST

Toutes les routes ci-dessous ont un slash final. Les erreurs de validation sont JSON. Une route API inconnue renvoie aussi une erreur JSON 404.

| Ressource | Routes et méthodes |
| --- | --- |
| Authentification | `POST /api/v1/auth/token/`, `GET /api/v1/auth/me/`, `POST /api/v1/auth/token/revoke/` |
| Bâtiments | `GET/POST /api/v1/buildings/`; `GET/PUT/PATCH/DELETE /api/v1/buildings/<id>/`; `POST /api/v1/buildings/<id>/archive/` |
| Espaces | `GET/POST /api/v1/spaces/`; `GET/PUT/PATCH/DELETE /api/v1/spaces/<id>/`; `POST /api/v1/spaces/<id>/archive/` |
| Capteurs | `GET/POST /api/v1/sensors/`; `GET/PUT/PATCH/DELETE /api/v1/sensors/<id>/`; `POST /api/v1/sensors/<id>/archive/`; `GET /api/v1/sensors/<id>/measurements/` |
| Mesures | `GET/POST /api/v1/measurements/`; `GET /api/v1/measurements/<id>/` |
| Actionneurs | `GET/POST /api/v1/actuators/`; `GET/PUT/PATCH/DELETE /api/v1/actuators/<id>/`; `POST /api/v1/actuators/<id>/archive/` |
| Commandes | `GET/POST /api/v1/actuator-commands/`; `GET /api/v1/actuator-commands/<id>/` |
| Dashboard | `GET /api/v1/dashboard/summary/`, `/environment/`, `/measurements/`, `/actuators/` |
| Simulateur | `GET /simulator/spaces/?building_id=<id>`, `POST /simulator/start/`, `POST /simulator/stop/`, `GET /simulator/status/` |

Les filtres de bâtiments et espaces sont `building` pour les espaces. Les filtres capteurs sont `sensor_type`, `space`, `building` et `is_active`. Les filtres de mesures sont `sensor`, `space`, `building`, `date_from`, `date_to` et `ordering=recorded_at` ou `-recorded_at`. Les filtres d’actionneurs sont `actuator_type`, `building`, `space` et `is_active`; ceux des commandes sont `actuator`, `status` et `command_type`. Les listes de mesures et commandes sont paginées à 20 lignes par défaut; `page_size` peut être configuré jusqu’à 100 (`SMARTFARM_MEASUREMENTS_PAGE_SIZE`).

Le dashboard présente les dernières valeurs enregistrées avec leur horodatage et ne les qualifie pas de temps réel. Le filtre du graphique accepte `period=24h` ou `period=7d` sur l’endpoint dashboard des mesures.

## Données environnementales

Les capteurs de température utilisent `°C` et sont limités techniquement à −50..80. Les capteurs d’humidité utilisent `%` et sont limités à 0..100. Ces limites physiques sont distinctes des seuils environnementaux configurés sur chaque capteur. Une mesure qui dépasse un seuil mais reste physiquement valide peut être enregistrée. Aucune alerte n’est générée.

## Simulateur

Sur `/simulator/`, choisissez un bâtiment, un espace, au moins un capteur actif et un intervalle entier d’au moins cinq secondes. Les valeurs décimales sont générées dans les plages normales configurables par variables d’environnement : `SMARTFARM_SIMULATOR_TEMPERATURE_MIN/MAX` (18..30 °C par défaut) et `SMARTFARM_SIMULATOR_HUMIDITY_MIN/MAX` (40..75 % par défaut). Les bornes sont ramenées aux limites physiques des modèles.

Chaque cycle envoie les mesures par HTTP à l’API existante. Le simulateur utilise un thread contrôlé côté serveur; le bouton Arrêter attend la fin de toute requête en cours, avec un timeout HTTP de cinq secondes. Le registre, le compteur et les erreurs sont en mémoire et limités au processus Django : gardez un seul serveur local actif pendant la simulation. Un redémarrage arrête la tâche et remet son état en mémoire à zéro. Les commandes d’actionneurs sont également des enregistrements simulés et ne pilotent aucun matériel.

## Tests et migrations

Depuis le dossier du projet :

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations
python manage.py test
```

Les tests utilisent une base temporaire; ils ne réinitialisent pas `db.sqlite3`.

## Limites connues

- SQLite et l’application sont destinés à un usage local et scolaire.
- La tâche du simulateur n’est pas persistante et ne fonctionne pas entre plusieurs processus de serveur.
- Aucune communication MQTT, ESP32 ou matérielle n’est mise en œuvre.
- Les commandes ON/OFF sont conservées comme historique, sans exécution physique.
- Aucun système d’alertes, gestion d’animaux individuels, Docker, PostgreSQL, Redis ou Celery n’est inclus.
- Les utilisateurs utilisent le système Django natif; aucun système de rôles personnalisé n’est prévu.
