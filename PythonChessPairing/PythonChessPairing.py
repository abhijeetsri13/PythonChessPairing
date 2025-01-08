import tkinter as tk
from tkinter import messagebox, filedialog, Toplevel, simpledialog
from tkinter.ttk import Treeview, Notebook
import csv
import uuid
import sqlite3
import json
import random

DB_FILE = "chess_tournaments.db"

class ChessApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Manager")
        self.conn = sqlite3.connect(DB_FILE)
        self.create_tables()
        self.cur_tourney = None
        self.init_ui()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Tournaments (
                TournamentID INTEGER PRIMARY KEY AUTOINCREMENT,
                TournamentName TEXT NOT NULL UNIQUE,
                CreatedDate DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Players (
                PlayerID INTEGER PRIMARY KEY AUTOINCREMENT,
                PlayerUUID TEXT UNIQUE NOT NULL,
                PlayerName TEXT NOT NULL,
                TournamentID INTEGER NOT NULL,
                FOREIGN KEY (TournamentID) REFERENCES Tournaments (TournamentID) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Rounds (
                RoundID INTEGER PRIMARY KEY AUTOINCREMENT,
                RoundNumber INTEGER NOT NULL,
                TournamentID INTEGER NOT NULL,
                Pairings TEXT NOT NULL, -- JSON format to store pairings
                Results TEXT, -- JSON format to store results
                FOREIGN KEY (TournamentID) REFERENCES Tournaments (TournamentID) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PlayerPoints (
                PlayerID INTEGER PRIMARY KEY,
                TournamentID INTEGER NOT NULL,
                Points REAL DEFAULT 0,
                FOREIGN KEY (PlayerID) REFERENCES Players (PlayerID) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    def init_ui(self):
        tk.Label(self.root, text="Tournaments").grid(row=0, column=0, padx=10, pady=5)
        self.t_list = Treeview(self.root, columns=("Name"), show="headings")
        self.t_list.heading("Name", text="Tournament")
        self.t_list.grid(row=1, column=0, padx=10, pady=5)
        self.t_list.bind("<Double-1>", self.open_t_window)
        tk.Button(self.root, text="Add", command=self.add_t).grid(row=2, column=0, padx=10, pady=5)
        tk.Button(self.root, text="Edit", command=self.edit_t).grid(row=3, column=0, padx=10, pady=5)
        tk.Button(self.root, text="Delete", command=self.del_t).grid(row=4, column=0, padx=10, pady=5)
        self.refresh_t_list()

    def add_t(self):
        name = simpledialog.askstring("Add Tournament", "Enter name:")
        if name:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO Tournaments (TournamentName) VALUES (?)", (name,))
                self.conn.commit()
                self.refresh_t_list()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Tournament name must be unique")

    def edit_t(self):
        sel = self.t_list.selection()
        if sel:
            cur = self.t_list.item(sel, "values")[0]
            new = simpledialog.askstring("Edit", "New name:", initialvalue=cur)
            if new:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE Tournaments SET TournamentName = ? WHERE TournamentName = ?", (new, cur))
                self.conn.commit()
                self.refresh_t_list()

    def del_t(self):
        sel = self.t_list.selection()
        if sel:
            name = self.t_list.item(sel, "values")[0]
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM Tournaments WHERE TournamentName = ?", (name,))
            self.conn.commit()
            self.refresh_t_list()

    def refresh_t_list(self):
        self.t_list.delete(*self.t_list.get_children())
        cursor = self.conn.cursor()
        cursor.execute("SELECT TournamentName FROM Tournaments")
        for row in cursor.fetchall():
            self.t_list.insert("", "end", values=(row[0],))

    def open_t_window(self, event):
        sel = self.t_list.selection()
        if not sel:
            messagebox.showerror("Error", "No tournament selected")
            return
        self.cur_tourney = self.t_list.item(sel, "values")[0]

        cursor = self.conn.cursor()
        cursor.execute("SELECT TournamentID FROM Tournaments WHERE TournamentName = ?", (self.cur_tourney,))
        tourney_id = cursor.fetchone()[0]

        win = Toplevel(self.root)
        win.title(f"Manage - {self.cur_tourney}")
        notebook = Notebook(win)
        notebook.pack(expand=True, fill="both")

        def manage_players():
            frame = tk.Frame(notebook)
            notebook.add(frame, text="Players")
            tk.Label(frame, text="Players", font=("Arial", 12, "bold")).pack(pady=5)
            p_list = Treeview(frame, columns=("Player UUID", "Name"), show="headings")
            p_list.heading("Player UUID", text="Player UUID")
            p_list.heading("Name", text="Name")
            p_list.pack(pady=5, expand=True, fill="both")

            def refresh_p_list():
                p_list.delete(*p_list.get_children())
                cursor = self.conn.cursor()
                cursor.execute("SELECT PlayerUUID, PlayerName FROM Players WHERE TournamentID = ?", (tourney_id,))
                for row in cursor.fetchall():
                    p_list.insert("", "end", values=(row[0], row[1]))

            def add_p():
                name = simpledialog.askstring("Add", "Player name:")
                if name:
                    player_uuid = str(uuid.uuid4())[:8]
                    cursor = self.conn.cursor()
                    cursor.execute(
                        "INSERT INTO Players (PlayerUUID, PlayerName, TournamentID) VALUES (?, ?, ?)",
                        (player_uuid, name, tourney_id),
                    )
                    cursor.execute(
                        "INSERT INTO PlayerPoints (PlayerID, TournamentID) SELECT PlayerID, ? FROM Players WHERE PlayerUUID = ?",
                        (tourney_id, player_uuid),
                    )
                    self.conn.commit()
                    refresh_p_list()

            def import_csv():
                path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
                if path:
                    try:
                        with open(path, "r") as file:
                            reader = csv.reader(file)
                            for row in reader:
                                if row:
                                    name = row[0].strip()
                                    player_uuid = str(uuid.uuid4())[:8]
                                    cursor = self.conn.cursor()
                                    cursor.execute(
                                        "INSERT INTO Players (PlayerUUID, PlayerName, TournamentID) VALUES (?, ?, ?)",
                                        (player_uuid, name, tourney_id),
                                    )
                                    cursor.execute(
                                        "INSERT INTO PlayerPoints (PlayerID, TournamentID) SELECT PlayerID, ? FROM Players WHERE PlayerUUID = ?",
                                        (tourney_id, player_uuid),
                                    )
                            self.conn.commit()
                            refresh_p_list()
                            messagebox.showinfo("Success", "Players imported from CSV")
                    except Exception as e:
                        messagebox.showerror("Error", str(e))

            ctrl = tk.Frame(frame)
            ctrl.pack(pady=10)
            tk.Button(ctrl, text="Add", command=add_p).grid(row=0, column=0, padx=5)
            tk.Button(ctrl, text="Import CSV", command=import_csv).grid(row=0, column=1, padx=5)
            refresh_p_list()

        def manage_rounds():
            frame = tk.Frame(notebook)
            notebook.add(frame, text="Rounds")
            tk.Label(frame, text="Rounds", font=("Arial", 12, "bold")).pack(pady=5)
            r_list = Treeview(frame, columns=("Round Number", "Pairings"), show="headings")
            r_list.heading("Round Number", text="Round Number")
            r_list.heading("Pairings", text="Pairings")
            r_list.pack(pady=5, expand=True, fill="both")

            def refresh_rounds():
                r_list.delete(*r_list.get_children())
                cursor = self.conn.cursor()
                cursor.execute("SELECT RoundID, RoundNumber, Pairings, Results FROM Rounds WHERE TournamentID = ?", (tourney_id,))
                for row in cursor.fetchall():
                    round_number = row[1]
                    pairings = row[2]
                    results = row[3] if row[3] else "Pending"
                    r_list.insert("", "end", values=(round_number, pairings, results))

            def generate_round():
                cursor = self.conn.cursor()
                cursor.execute("SELECT PlayerID, Points FROM PlayerPoints WHERE TournamentID = ? ORDER BY Points DESC, PlayerID ASC", (tourney_id,))
                players = [row[0] for row in cursor.fetchall()]

                if len(players) < 2:
                    messagebox.showerror("Error", "Not enough players for pairing")
                    return

                # Create a new round number
                cursor.execute("SELECT COUNT(*) FROM Rounds WHERE TournamentID = ?", (tourney_id,))
                round_number = cursor.fetchone()[0] + 1

                # FIDE-compliant Swiss pairing logic
                pairings = []
                used = set()
                for i, player1 in enumerate(players):
                    if player1 in used:
                        continue
                    for player2 in players[i + 1:]:
                        if player2 in used:
                            continue
                        pairings.append((player1, player2))
                        used.add(player1)
                        used.add(player2)
                        break

                # If an odd number of players, the last player gets a bye
                if len(used) < len(players):
                    for player in players:
                        if player not in used:
                            pairings.append((player, None))
                            break

                pairings_json = json.dumps(pairings)
                cursor.execute(
                    "INSERT INTO Rounds (RoundNumber, TournamentID, Pairings) VALUES (?, ?, ?)",
                    (round_number, tourney_id, pairings_json),
                )
                self.conn.commit()
                refresh_rounds()

            def update_results():
                sel = r_list.selection()
                if not sel:
                    messagebox.showerror("Error", "No round selected")
                    return

                round_id = r_list.item(sel, "values")[0]
                pairings_json = r_list.item(sel, "values")[1]
                results_json = r_list.item(sel, "values")[2]

                pairings = json.loads(pairings_json)
                existing_results = json.loads(results_json) if results_json and results_json != "Pending" else []

                # Convert existing_results to a dictionary for easy access
                results_dict = {}
                for result in existing_results:
                    results_dict[(result.get("white_id"), result.get("black_id"))] = (result.get("white_points", 0), result.get("black_points", 0))

                results = []

                def save_results():
                    cursor = self.conn.cursor()
                    for white_id, black_id, white_var, black_var in results:
                        white_points = white_var.get()
                        black_points = black_var.get()

                        # Save results for each pairing
                        if white_id is not None:
                            cursor.execute(
                                "UPDATE PlayerPoints SET Points = Points + ? WHERE PlayerID = ? AND TournamentID = ?",
                                (white_points, white_id, tourney_id),
                            )
                        if black_id is not None:
                            cursor.execute(
                                "UPDATE PlayerPoints SET Points = Points + ? WHERE PlayerID = ? AND TournamentID = ?",
                                (black_points, black_id, tourney_id),
                            )

                    # Save results as JSON in the Rounds table
                    results_json = json.dumps([
                        {
                            "white_id": white_id,
                            "black_id": black_id,
                            "white_points": white_var.get(),
                            "black_points": black_var.get(),
                        }
                        for white_id, black_id, white_var, black_var in results
                    ])
                    cursor.execute("UPDATE Rounds SET Results = ? WHERE RoundID = ?", (results_json, round_id))

                    self.conn.commit()
                    refresh_rounds()
                    result_window.destroy()

                result_window = Toplevel(self.root)
                result_window.title("Update Results")

                for i, (white_id, black_id) in enumerate(pairings):
                    cursor.execute("SELECT PlayerName FROM Players WHERE PlayerID = ?", (white_id,))
                    white_name = cursor.fetchone()[0]
                    black_name = None
                    if black_id:
                        cursor.execute("SELECT PlayerName FROM Players WHERE PlayerID = ?", (black_id,))
                        black_name = cursor.fetchone()[0]

                    tk.Label(result_window, text=f"{white_name} vs {black_name if black_name else 'Bye'}").grid(row=i, column=0, padx=10, pady=5)

                    white_points, black_points = results_dict.get((white_id, black_id), (0, 0))

                    white_var = tk.DoubleVar(value=white_points)
                    black_var = tk.DoubleVar(value=black_points)

                    tk.Entry(result_window, textvariable=white_var).grid(row=i, column=1, padx=5)
                    tk.Label(result_window, text="-").grid(row=i, column=2, padx=5)
                    tk.Entry(result_window, textvariable=black_var).grid(row=i, column=3, padx=5)

                    results.append((white_id, black_id, white_var, black_var))

                tk.Button(result_window, text="Save Results", command=save_results).grid(row=len(pairings) + 1, column=1, pady=10)

            def view_results():
                sel = r_list.selection()
                if not sel:
                    messagebox.showerror("Error", "No round selected")
                    return

                round_id = r_list.item(sel, "values")[0]
                results_json = r_list.item(sel, "values")[2]

                if not results_json or results_json == "Pending":
                    messagebox.showinfo("Results", "No results available for this round yet.")
                    return

                results = json.loads(results_json)

                result_window = Toplevel(self.root)
                result_window.title(f"Results - Round {round_id}")

                for i, result in enumerate(results):
                    white_id = result["white_id"]
                    black_id = result["black_id"]

                    cursor.execute("SELECT PlayerName FROM Players WHERE PlayerID = ?", (white_id,))
                    white_name = cursor.fetchone()[0]

                    black_name = "Bye"
                    if black_id:
                        cursor.execute("SELECT PlayerName FROM Players WHERE PlayerID = ?", (black_id,))
                        black_name = cursor.fetchone()[0]

                    white_points = result["white_points"]
                    black_points = result["black_points"]

                    tk.Label(result_window, text=f"{white_name} ({white_points}) vs {black_name} ({black_points})").grid(row=i, column=0, padx=10, pady=5)

            ctrl = tk.Frame(frame)
            ctrl.pack(pady=10)
            tk.Button(ctrl, text="Generate Round", command=generate_round).grid(row=0, column=0, padx=5)
            tk.Button(ctrl, text="Update Results", command=update_results).grid(row=0, column=1, padx=5)
            tk.Button(ctrl, text="View Results", command=view_results).grid(row=0, column=2, padx=5)
            refresh_rounds()

        def manage_standings():
            frame = tk.Frame(notebook)
            notebook.add(frame, text="Standings")
            tk.Label(frame, text="Standings", font=("Arial", 12, "bold")).pack(pady=5)
            standings_list = Treeview(frame, columns=("Rank", "Player", "Points", "Buchholz", "Wins"), show="headings")
            standings_list.heading("Rank", text="Rank")
            standings_list.heading("Player", text="Player")
            standings_list.heading("Points", text="Points")
            standings_list.heading("Buchholz", text="Buchholz")
            standings_list.heading("Wins", text="Wins")
            standings_list.pack(pady=5, expand=True, fill="both")

            def refresh_standings():
                standings_list.delete(*standings_list.get_children())
                cursor = self.conn.cursor()

                # 1) Fetch all players in the tournament
                cursor.execute("""
                    SELECT Players.PlayerID, Players.PlayerName, PlayerPoints.Points
                    FROM PlayerPoints
                    JOIN Players ON PlayerPoints.PlayerID = Players.PlayerID
                    WHERE PlayerPoints.TournamentID = ?
                """, (tourney_id,))
                players_data = cursor.fetchall()

                # Convert to dict for easy lookup: {player_id: {"name": ..., "points": ..., "buchholz": 0, "wins": 0}}
                players_dict = {}
                for pid, pname, pts in players_data:
                    players_dict[pid] = {
                        "name": pname,
                        "points": pts,
                        "buchholz": 0,
                        "wins": 0
                    }

                # 2) Fetch all rounds for this tournament
                cursor.execute("SELECT RoundID, Pairings, Results FROM Rounds WHERE TournamentID = ?", (tourney_id,))
                rounds_data = cursor.fetchall()

                # 3) Build a mapping of opponents (for Buchholz) and track wins
                #    We'll go round by round, pairing by pairing.
                for (round_id, pairings_json, results_json) in rounds_data:
                    try:
                        pairings = json.loads(pairings_json)
                    except:
                        pairings = []

                    if not results_json or results_json == "Pending":
                        # No results yet, so no wins to update and no guaranteed opponents
                        # (some might not have played if they had a bye)
                        continue
                    else:
                        results = json.loads(results_json)

                    # Build a dict for easy results lookup:
                    #   key = (white_id, black_id),
                    #   value = (white_points, black_points)
                    results_dict = {}
                    for r in results:
                        w_id = r.get("white_id")
                        b_id = r.get("black_id")
                        w_pts = r.get("white_points", 0)
                        b_pts = r.get("black_points", 0)
                        results_dict[(w_id, b_id)] = (w_pts, b_pts)

                    # pairings is a list of tuples: (white_id, black_id)
                    for (white_id, black_id) in pairings:
                        if white_id is None or black_id is None:
                            # bye situation
                            continue
                        if (white_id, black_id) not in results_dict:
                            # No result stored? skip
                            continue

                        w_pts, b_pts = results_dict[(white_id, black_id)]

                        # 3.1) Update WINS
                        # If white had a full point:
                        if w_pts == 1.0 and white_id in players_dict:
                            players_dict[white_id]["wins"] += 1
                        # If black had a full point:
                        if b_pts == 1.0 and black_id in players_dict:
                            players_dict[black_id]["wins"] += 1

                        # 3.2) Each is an opponent to the other, so for Buchholz later
                        # We'll store them in a structure so we can sum up their final points.
                        # For instance, keep a dict of opponents:
                        #   players_opponents = { pid1: set([opp1, opp2, ...]), pid2: set([...]) }
                        # We'll define it outside the round loop:
                        if "opponents" not in players_dict[white_id]:
                            players_dict[white_id]["opponents"] = set()
                        if "opponents" not in players_dict[black_id]:
                            players_dict[black_id]["opponents"] = set()

                        players_dict[white_id]["opponents"].add(black_id)
                        players_dict[black_id]["opponents"].add(white_id)

                # 4) Once we've processed all rounds, we now compute Buchholz for each player
                for pid, data in players_dict.items():
                    opp_ids = data.get("opponents", [])
                    buchholz = 0
                    for opp_id in opp_ids:
                        if opp_id in players_dict:
                            buchholz += players_dict[opp_id]["points"]
                    players_dict[pid]["buchholz"] = buchholz

                # 5) Build a final list (player_name, points, buchholz, wins) and sort
                standings = []
                for pid, data in players_dict.items():
                    pname = data["name"]
                    pts = data["points"]
                    bch = data["buchholz"]
                    wns = data["wins"]
                    standings.append((pname, pts, bch, wns))

                # Sort by (descending points, descending buchholz, descending wins)
                #  i.e. the best is first
                standings.sort(key=lambda x: (-x[1], -x[2], -x[3]))

                # 6) Insert into the standings Treeview
                for rank, (player_name, points, buchholz, wins) in enumerate(standings, start=1):
                    standings_list.insert(
                        "",
                        "end",
                        values=(rank, player_name, points, buchholz, wins)
                    )





            refresh_standings()

        manage_players()
        manage_rounds()
        manage_standings()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessApp(root)
    root.mainloop()
