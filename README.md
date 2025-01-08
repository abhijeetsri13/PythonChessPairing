
# Chess Tournament Pairing Application

## Overview

The Chess Tournament Pairing Application is a Python-based GUI application designed for managing chess tournaments efficiently. It offers features like creating tournaments, managing players, generating Swiss pairings, updating results, and viewing standings. All tournament data is stored persistently using SQLite.

---

## Features

- **Tournament Management**:
  - Create, edit, and delete tournaments.
  - View a list of all tournaments.

- **Player Management**:
  - Add players manually or import them via CSV files.
  - Automatically assign a unique identifier (UUID) to each player.
  - Maintain player scores within tournaments.

- **Round Management**:
  - Generate rounds with FIDE-compliant Swiss pairings.
  - Update results for each round with an intuitive interface.
  - View results of individual rounds.

- **Standings**:
  - Display tournament standings with details like:
    - Player points.
    - Buchholz score.
    - Total wins.

- **Data Persistence**:
  - All data is saved in an SQLite database for long-term storage and retrieval.

---

## Technologies Used

- **Programming Language**: Python
- **Database**: SQLite
- **GUI Framework**: Tkinter

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/chess-tournament-pairing.git
   cd chess-tournament-pairing
   ```

2. **Install Dependencies**:
   Ensure Python 3.x is installed on your system. Install required libraries using pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**:
   ```bash
   python PythonChessPairing.py
   ```

---

## Usage

### Starting the Application
- Run the script: `python PythonChessPairing.py`.
- The main interface allows you to create and manage tournaments.

### Key Functionalities
1. **Tournaments**:
   - Create new tournaments using the "Add" button.
   - Edit or delete existing tournaments.

2. **Players**:
   - Add players manually or import from CSV files.
   - Manage player details for each tournament.

3. **Rounds**:
   - Generate pairings for rounds automatically.
   - Update and save results for each round.
   - View results of past rounds.

4. **Standings**:
   - View tournament standings with details like points, Buchholz scores, and wins.

---

## File Structure

- `PythonChessPairing.py`: Main script containing the application logic.
- `chess_tournaments.db`: SQLite database file for storing tournament data.
- **Folders for Resources**:
  - Add any relevant CSV files for player data import here.

---

## Contributing

Feel free to fork this repository and make improvements. Submit a pull request for review.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Screenshots

*(Add screenshots of your application here for better visualization.)*
