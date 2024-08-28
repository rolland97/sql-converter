# SQL to PHP Array Converter

This Docker-based FastAPI web application converts SQL INSERT statements into PHP arrays. It provides a simple web interface for uploading SQL files and returns a PHP file containing the converted data structures.

## Features

- Docker-containerized for easy deployment and consistency across environments
- Web-based interface for easy file upload
- Converts SQL INSERT statements to PHP arrays
- Handles multiple tables in a single SQL file
- Properly manages NULL values and empty strings
- Returns the converted data as a downloadable PHP file
- Automatically cleans up temporary files

## Requirements

- Docker
- Docker Compose (optional, but recommended)

## Installation and Setup

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/sql-to-php-converter.git
   cd sql-to-php-converter
   ```

2. Build the Docker image:
   ```
   docker build -t sql-to-php-converter .
   ```

## Usage

### Using Docker Run

1. Start the container:
   ```
   docker run -d -p 8000:8000 sql-to-php-converter
   ```

2. Open a web browser and navigate to `http://localhost:8000`

### Using Docker Compose (Recommended)

1. Start the services defined in `docker-compose.yml`:
   ```
   docker-compose up -d
   ```

2. Open a web browser and navigate to `http://localhost:8000`

3. Use the web interface to upload your SQL file containing INSERT statements

4. The application will process the file and return a converted PHP file for download

## API Endpoints

- `GET /`: Renders the HTML form for file upload
- `POST /convert/`: Accepts a SQL file upload, converts it, and returns the PHP file

## File Structure

- `app.py`: Main application file containing the FastAPI app and all the logic
- `Dockerfile`: Defines how to build the Docker image for this application
- `docker-compose.yml`: Defines the services, networks, and volumes for Docker Compose
- `requirements.txt`: Lists the Python dependencies for the project
- `README.md`: This file, containing project documentation

## Development

To make changes to the application:

1. Modify the code in `app.py`
2. Rebuild the Docker image:
   ```
   docker build -t sql-to-php-converter .
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