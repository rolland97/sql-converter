# SQL Converter

This Docker-based FastAPI web application provides two conversion utilities:
1. Converts SQL INSERT statements into PHP arrays
2. Converts SQL CREATE TABLE statements into Laravel migrations

It offers a simple web interface with tabs for easy access to both features.

## Features

- Docker-containerized for easy deployment and consistency across environments
- Web-based interface with tabbed layout for easy access to both conversion utilities
- Converts SQL INSERT statements to PHP arrays
- Converts SQL CREATE TABLE statements to Laravel migrations
- Handles multiple tables in a single SQL file
- Properly manages NULL values and empty strings
- Returns the converted data as downloadable files (PHP file or ZIP file for migrations)
- Automatically cleans up temporary files

## Requirements

- Docker
- Docker Compose (optional, but recommended)

## Installation and Setup

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/sql-converter.git
   cd sql-converter
   ```

2. Build the Docker image:
   ```
   docker build -t sql-converter .
   ```

## Usage

### Using Docker Run

1. Start the container:
   ```
   docker run -d -p 8000:8000 sql-converter
   ```

2. Open a web browser and navigate to `http://localhost:8000`

### Using Docker Compose (Recommended)

1. Start the services defined in `docker-compose.yml`:
   ```
   docker-compose up -d
   ```

2. Open a web browser and navigate to `http://localhost:8000`

3. Use the web interface to choose between SQL to PHP Array or SQL to Laravel Migration conversion

4. Upload your SQL file containing either INSERT or CREATE TABLE statements

5. The application will process the file and return a converted file for download (PHP file or ZIP file)

## API Endpoints

- `GET /`: Renders the HTML page with tabs for both conversion options
- `POST /convert/php`: Accepts a SQL file upload, converts INSERT statements to PHP arrays, and returns a PHP file
- `POST /convert/laravel`: Accepts a SQL file upload, converts CREATE TABLE statements to Laravel migrations, and returns a ZIP file

## File Structure

- `app.py`: Main application file containing the FastAPI app and all the logic
- `Dockerfile`: Defines how to build the Docker image for this application
- `docker-compose.yml`: Defines the services, networks, and volumes for Docker Compose
- `requirements.txt`: Lists the Python dependencies for the project
- `static/styles.css`: CSS file for styling the web interface
- `README.md`: This file, containing project documentation

## Development

To make changes to the application:

1. Modify the code in `app.py` or `static/styles.css`
2. Rebuild the Docker image:
   ```
   docker build -t sql-converter .
   ```
3. Restart your container or Docker Compose services

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Uvicorn](https://www.uvicorn.org/) for the ASGI server
- [Docker](https://www.docker.com/) for containerization