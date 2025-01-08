import tkinter as tk
from tkinter import (
    messagebox, filedialog, Toplevel, simpledialog, Scrollbar
)
from tkinter.ttk import Treeview, Notebook
import csv
import uuid
import sqlite3
import json
import os

DB_FILE = "chess_tournaments.db"

# -------------------------------------------------------------------
#                            DATABASE
# -------------------------------------------------------------------

class ChessDB:
    """
    Encapsulates all DB-related operations.
    Supports:
      - Late joiners via Players.JoinedRound
      - Basic round generation & results
      - Updating pairings and results in Rounds
    """
    def __init__(self, db_file: str):
        self.conn = sqlite3.connect(db_file)
        self.create_tables()

    def create_tables(self) -> None:
        """
        Creates all required tables, including a JoinedRound column in 'Players'
        for players who come after round 1.
        """
        with self.conn:
            # Tournaments
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS Tournaments (
                    TournamentID INTEGER PRIMARY KEY AUTOINCREMENT,
                    TournamentName TEXT NOT NULL UNIQUE,
                    CreatedDate DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Players
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS Players (
                    PlayerID INTEGER PRIMARY KEY AUTOINCREMENT,
                    PlayerUUID TEXT UNIQUE NOT NULL,
                    PlayerName TEXT NOT NULL,
                    TournamentID INTEGER NOT NULL,
                    JoinedRound INTEGER DEFAULT 1,    -- NEW: for late joining
                    FOREIGN KEY (TournamentID) REFERENCES Tournaments (TournamentID)
                        ON DELETE CASCADE
                )
            """)

            # Rounds
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS Rounds (
                    RoundID INTEGER PRIMARY KEY AUTOINCREMENT,
                    RoundNumber INTEGER NOT NULL,
                    TournamentID INTEGER NOT NULL,
                    Pairings TEXT NOT NULL,   -- JSON: list of (white_id, black_id)
                    Results TEXT,            -- JSON: list of { white_id, black_id, white_points, black_points }
                    FOREIGN KEY (TournamentID) REFERENCES Tournaments (TournamentID)
                        ON DELETE CASCADE
                )
            """)

            # PlayerPoints
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS PlayerPoints (
                    PlayerID INTEGER NOT NULL,
                    TournamentID INTEGER NOT NULL,
                    Points REAL DEFAULT 0,
                    PRIMARY KEY (PlayerID, TournamentID),
                    FOREIGN KEY (PlayerID) REFERENCES Players (PlayerID) ON DELETE CASCADE
                )
            """)

    # ----------------------
    # Tournaments
    # ----------------------
    def add_tournament(self, name: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO Tournaments (TournamentName) VALUES (?)",
                (name,)
            )

    def edit_tournament(self, old_name: str, new_name: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE Tournaments SET TournamentName = ? WHERE TournamentName = ?",
                (new_name, old_name)
            )

    def delete_tournament(self, name: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM Tournaments WHERE TournamentName = ?",
                (name,)
            )

    def get_tournaments(self):
        cur = self.conn.cursor()
        cur.execute("SELECT TournamentName FROM Tournaments")
        return cur.fetchall()

    def get_tournament_id_by_name(self, name: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT TournamentID FROM Tournaments WHERE TournamentName = ?",
            (name,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    # ----------------------
    # Players
    # ----------------------
    def add_player(self, name: str, tourney_id: int, joined_round: int = 1) -> None:
        """
        Adds a new player who begins participating at 'joined_round'.
        """
        player_uuid = str(uuid.uuid4())[:8]
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO Players (PlayerUUID, PlayerName, TournamentID, JoinedRound)
                VALUES (?, ?, ?, ?)
                """,
                (player_uuid, name, tourney_id, joined_round)
            )
            self.conn.execute(
                """
                INSERT INTO PlayerPoints (PlayerID, TournamentID)
                SELECT PlayerID, ?
                FROM Players
                WHERE PlayerUUID = ?
                """,
                (tourney_id, player_uuid)
            )

    def import_players_from_csv(self, path: str, tourney_id: int) -> None:
        with open(path, "r") as file:
            reader = csv.reader(file)
            with self.conn:
                for row in reader:
                    if row:
                        name = row[0].strip()
                        player_uuid = str(uuid.uuid4())[:8]
                        self.conn.execute(
                            """
                            INSERT INTO Players (PlayerUUID, PlayerName, TournamentID)
                            VALUES (?, ?, ?)
                            """,
                            (player_uuid, name, tourney_id)
                        )
                        self.conn.execute(
                            """
                            INSERT INTO PlayerPoints (PlayerID, TournamentID)
                            SELECT PlayerID, ? 
                            FROM Players 
                            WHERE PlayerUUID = ?
                            """,
                            (tourney_id, player_uuid)
                        )

    def get_players_for_tournament(self, tourney_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT PlayerUUID, PlayerName
            FROM Players
            WHERE TournamentID = ?
        """, (tourney_id,))
        return cur.fetchall()

    # ----------------------
    # Rounds
    # ----------------------
    def get_rounds_for_tournament(self, tourney_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT RoundID, RoundNumber, Pairings, Results
            FROM Rounds
            WHERE TournamentID = ?
        """, (tourney_id,))
        return cur.fetchall()

    def create_round(self, tourney_id: int, round_number: int, pairings: list) -> int:
        """
        Insert a new row in Rounds with these pairings. Return the new RoundID.
        """
        pairings_json = json.dumps(pairings)
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO Rounds (RoundNumber, TournamentID, Pairings)
            VALUES (?, ?, ?)
        """, (round_number, tourney_id, pairings_json))
        self.conn.commit()
        return cur.lastrowid

    def update_round_pairings(self, round_id: int, new_pairings: list) -> None:
        """
        Update the Pairings (JSON) for an existing round, without overwriting Results.
        """
        pairings_json = json.dumps(new_pairings)
        with self.conn:
            self.conn.execute("""
                UPDATE Rounds
                SET Pairings = ?
                WHERE RoundID = ?
            """, (pairings_json, round_id))

    def update_round_results(self, round_id: int, results_data: list) -> None:
        results_json = json.dumps(results_data)
        with self.conn:
            self.conn.execute("""
                UPDATE Rounds
                SET Results = ?
                WHERE RoundID = ?
            """, (results_json, round_id))

    # ----------------------
    # Points & Standings
    # ----------------------
    def get_sorted_players_by_points(self, tourney_id: int, joined_round: int = None):
        """
        Returns (PlayerID, Points) sorted by descending points, then ascending PlayerID.
        If joined_round is given, only players with JoinedRound <= joined_round are included.
        """
        cur = self.conn.cursor()
        if joined_round is not None:
            sql = """
                SELECT p.PlayerID, pp.Points
                FROM PlayerPoints pp
                JOIN Players p ON pp.PlayerID = p.PlayerID
                WHERE pp.TournamentID = ?
                  AND p.JoinedRound <= ?
                ORDER BY pp.Points DESC, p.PlayerID ASC
            """
            cur.execute(sql, (tourney_id, joined_round))
        else:
            sql = """
                SELECT PlayerID, Points
                FROM PlayerPoints
                WHERE TournamentID = ?
                ORDER BY Points DESC, PlayerID ASC
            """
            cur.execute(sql, (tourney_id,))
        return cur.fetchall()

    def update_player_points(self, player_id: int, tourney_id: int, points_to_add: float) -> None:
        with self.conn:
            self.conn.execute("""
                UPDATE PlayerPoints
                SET Points = Points + ?
                WHERE PlayerID = ? AND TournamentID = ?
            """, (points_to_add, player_id, tourney_id))

    def get_all_players_with_points(self, tourney_id: int):
        """
        Returns list of (PlayerID, PlayerName, Points) for all players in a tournament.
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT pl.PlayerID, pl.PlayerName, pp.Points
            FROM PlayerPoints pp
            JOIN Players pl ON pp.PlayerID = pl.PlayerID
            WHERE pp.TournamentID = ?
        """, (tourney_id,))
        return cur.fetchall()

    def get_player_name(self, player_id: int):
        """
        Utility: returns the player's name or None if not found.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT PlayerName FROM Players WHERE PlayerID = ?", (player_id,))
        row = cur.fetchone()
        return row[0] if row else None


# -------------------------------------------------------------------
#                DRAG-AND-DROP PAIRING EDITOR
# -------------------------------------------------------------------

class PairingEditor(tk.Toplevel):
    """
    A window that displays pairings in a Treeview (row = one pair) and
    allows reordering entire pairs via drag-and-drop.
    """
    def __init__(self, master, db: ChessDB, round_id: int, initial_pairings: list, on_save_callback=None):
        """
        :param master: parent window
        :param db: reference to ChessDB
        :param round_id: which round we are editing
        :param initial_pairings: list of (white_id, black_id)
        :param on_save_callback: function to call after saving
        """
        super().__init__(master)
        self.title("Edit Pairings")
        self.db = db
        self.round_id = round_id
        self.on_save_callback = on_save_callback

        # We'll store (white_id, black_id) in self.pairings, in a certain order
        self.pairings = initial_pairings[:]  # copy

        # Setup Treeview
        self.tree = Treeview(self, columns=("White", "Black"), show="headings", height=10)
        self.tree.heading("White", text="White Player")
        self.tree.heading("Black", text="Black Player")
        self.tree.column("White", width=150)
        self.tree.column("Black", width=150)

        scroll_y = Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # Populate
        self.populate_tree()

        # Dragging state
        self._dragging_item = None
        self._dragging_iid = None

        # Bind events for row-based DnD
        self.tree.bind("<ButtonPress-1>", self.on_button_press)
        self.tree.bind("<B1-Motion>", self.on_mouse_move)
        self.tree.bind("<ButtonRelease-1>", self.on_button_release)

        # Save button
        tk.Button(self, text="Save Pairings", command=self.save_and_close).pack(pady=5)

    def populate_tree(self):
        """Refresh the Treeview from self.pairings."""
        self.tree.delete(*self.tree.get_children())
        for idx, (white_id, black_id) in enumerate(self.pairings):
            wname = self.db.get_player_name(white_id) if white_id else "Bye"
            bname = self.db.get_player_name(black_id) if black_id else "Bye"
            self.tree.insert("", "end", iid=str(idx), values=(wname, bname))

    def on_button_press(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        self._dragging_iid = self.tree.identify_row(event.y)
        if not self._dragging_iid:
            return
        self._dragging_item = int(self._dragging_iid)

    def on_mouse_move(self, event):
        # Could implement "ghost row" or highlight here.
        if self._dragging_item is None:
            return

    def on_button_release(self, event):
        if self._dragging_item is None:
            return

        target_iid = self.tree.identify_row(event.y)
        if not target_iid or target_iid == self._dragging_iid:
            # No move
            self._dragging_item = None
            self._dragging_iid = None
            return

        source_idx = self._dragging_item
        target_idx = int(target_iid)

        # Reorder in self.pairings
        pair = self.pairings.pop(source_idx)
        self.pairings.insert(target_idx, pair)

        self.populate_tree()

        # Reset
        self._dragging_item = None
        self._dragging_iid = None

    def save_and_close(self):
        """
        Updates the Rounds table Pairings JSON with the new order, calls callback, then closes.
        """
        self.db.update_round_pairings(self.round_id, self.pairings)

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()


# -------------------------------------------------------------------
#                    MAIN APPLICATION (ChessApp)
# -------------------------------------------------------------------

class ChessApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Chess Manager")
        self.db = ChessDB(DB_FILE)
        self.cur_tourney = None  # holds the currently selected tournament name
        self.init_ui()

    def init_ui(self) -> None:
        tk.Label(self.root, text="Tournaments").grid(row=0, column=0, padx=10, pady=5)

        # Treeview for tournaments
        self.t_list = Treeview(self.root, columns=("Name",), show="headings")
        self.t_list.heading("Name", text="Tournament")
        self.t_list.grid(row=1, column=0, padx=10, pady=5)
        self.t_list.bind("<Double-1>", self.open_t_window)

        # Buttons
        tk.Button(self.root, text="Add", command=self.add_t).grid(row=2, column=0, padx=5, pady=2, sticky="ew")
        tk.Button(self.root, text="Edit", command=self.edit_t).grid(row=3, column=0, padx=5, pady=2, sticky="ew")
        tk.Button(self.root, text="Delete", command=self.del_t).grid(row=4, column=0, padx=5, pady=2, sticky="ew")

        self.refresh_t_list()

    # ----------------------------------------------------------------
    #                       Tournaments
    # ----------------------------------------------------------------

    def refresh_t_list(self) -> None:
        self.t_list.delete(*self.t_list.get_children())
        for (name,) in self.db.get_tournaments():
            self.t_list.insert("", "end", values=(name,))

    def add_t(self) -> None:
        name = simpledialog.askstring("Add Tournament", "Enter name:")
        if name:
            name = name.strip()
            if not name:
                messagebox.showerror("Error", "Tournament name cannot be empty.")
                return
            try:
                self.db.add_tournament(name)
                self.refresh_t_list()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Tournament name must be unique")

    def edit_t(self) -> None:
        sel = self.t_list.selection()
        if not sel:
            messagebox.showerror("Error", "No tournament selected")
            return

        old_name = self.t_list.item(sel, "values")[0]
        new_name = simpledialog.askstring("Edit", "New name:", initialvalue=old_name)
        if new_name:
            new_name = new_name.strip()
            if not new_name:
                messagebox.showerror("Error", "Tournament name cannot be empty.")
                return
            self.db.edit_tournament(old_name, new_name)
            self.refresh_t_list()

    def del_t(self) -> None:
        sel = self.t_list.selection()
        if not sel:
            messagebox.showerror("Error", "No tournament selected")
            return
        name = self.t_list.item(sel, "values")[0]

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{name}'?"):
            return

        self.db.delete_tournament(name)
        self.refresh_t_list()

    def open_t_window(self, event=None) -> None:
        sel = self.t_list.selection()
        if not sel:
            messagebox.showerror("Error", "No tournament selected")
            return

        self.cur_tourney = self.t_list.item(sel, "values")[0]
        tourney_id = self.db.get_tournament_id_by_name(self.cur_tourney)
        if not tourney_id:
            messagebox.showerror("Error", "Could not find tournament ID.")
            return

        win = Toplevel(self.root)
        win.title(f"Manage - {self.cur_tourney}")
        notebook = Notebook(win)
        notebook.pack(expand=True, fill="both")

        self.build_players_tab(notebook, tourney_id)
        self.build_rounds_tab(notebook, tourney_id)
        self.build_standings_tab(notebook, tourney_id)

    # ----------------------------------------------------------------
    #                       Players Tab
    # ----------------------------------------------------------------

    def build_players_tab(self, notebook: Notebook, tourney_id: int) -> None:
        frame = tk.Frame(notebook)
        notebook.add(frame, text="Players")

        tk.Label(frame, text="Players", font=("Arial", 12, "bold")).pack(pady=5)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        p_list = Treeview(tree_frame, columns=("Player UUID", "Name"), show="headings")
        p_list.heading("Player UUID", text="Player UUID")
        p_list.heading("Name", text="Name")
        p_list.column("Player UUID", width=120, anchor=tk.W)
        p_list.column("Name", width=200, anchor=tk.W)

        scroll_y = Scrollbar(tree_frame, orient="vertical", command=p_list.yview)
        p_list.configure(yscrollcommand=scroll_y.set)

        scroll_y.pack(side="right", fill="y")
        p_list.pack(side="left", fill="both", expand=True)

        def refresh_p_list():
            p_list.delete(*p_list.get_children())
            players = self.db.get_players_for_tournament(tourney_id)
            for (uuid_, name) in players:
                p_list.insert("", "end", values=(uuid_, name))

        def add_p():
            name = simpledialog.askstring("Add Player", "Player name:")
            if name:
                name = name.strip()
                if not name:
                    messagebox.showerror("Error", "Player name cannot be empty.")
                    return

                joined_round_str = simpledialog.askstring(
                    "Joined Round",
                    "Which round is this player joining from? (Default = 1)"
                )
                if joined_round_str is None or not joined_round_str.strip():
                    joined_round = 1
                else:
                    try:
                        joined_round = int(joined_round_str)
                    except ValueError:
                        messagebox.showerror("Error", "Invalid round number.")
                        return

                self.db.add_player(name, tourney_id, joined_round)
                refresh_p_list()

        def import_csv():
            path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
            if path:
                try:
                    self.db.import_players_from_csv(path, tourney_id)
                    refresh_p_list()
                    messagebox.showinfo("Success", "Players imported from CSV")
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        ctrl = tk.Frame(frame)
        ctrl.pack(pady=10)
        tk.Button(ctrl, text="Add", command=add_p).grid(row=0, column=0, padx=5)
        tk.Button(ctrl, text="Import CSV", command=import_csv).grid(row=0, column=1, padx=5)

        refresh_p_list()

    # ----------------------------------------------------------------
    #                       Rounds Tab
    # ----------------------------------------------------------------

    def build_rounds_tab(self, notebook: Notebook, tourney_id: int) -> None:
        frame = tk.Frame(notebook)
        notebook.add(frame, text="Rounds")

        tk.Label(frame, text="Rounds", font=("Arial", 12, "bold")).pack(pady=5)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        r_list = Treeview(
            tree_frame,
            columns=("RoundID", "Round Number", "Pairings", "Results"),
            show="headings"
        )
        r_list.heading("RoundID", text="RoundID")
        r_list.heading("Round Number", text="Round Number")
        r_list.heading("Pairings", text="Pairings")
        r_list.heading("Results", text="Results")

        r_list.column("RoundID", width=0, stretch=False)
        r_list.column("Round Number", width=100, anchor=tk.CENTER)
        r_list.column("Pairings", width=200, anchor=tk.W)
        r_list.column("Results", width=150, anchor=tk.W)

        scroll_y = Scrollbar(tree_frame, orient="vertical", command=r_list.yview)
        r_list.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        r_list.pack(side="left", fill="both", expand=True)

        def refresh_rounds():
            r_list.delete(*r_list.get_children())
            rounds = self.db.get_rounds_for_tournament(tourney_id)
            for (round_id, round_number, pairings_json, results_json) in rounds:
                pairings = pairings_json
                results = results_json if results_json else "Pending"
                r_list.insert("", "end", values=(round_id, round_number, pairings, results))

        def generate_round():
            existing_rounds = self.db.get_rounds_for_tournament(tourney_id)
            next_round_number = len(existing_rounds) + 1

            # Only players who have joined <= next_round_number
            player_points = self.db.get_sorted_players_by_points(tourney_id, joined_round=next_round_number)
            players = [p[0] for p in player_points]

            if len(players) < 2:
                messagebox.showerror("Error", f"Not enough eligible players for Round {next_round_number}")
                return

            # Avoid repeated matchups: build a set of played pairs
            played_pairs = set()
            for (_, _, old_pairings_json, _) in existing_rounds:
                try:
                    old_pairings = json.loads(old_pairings_json)
                except:
                    old_pairings = []
                for (p1, p2) in old_pairings:
                    if p1 and p2:
                        played_pairs.add(tuple(sorted([p1, p2])))

            # Simple pairing logic
            pairings = []
            used = set()
            for i, p1 in enumerate(players):
                if p1 in used:
                    continue
                found_opponent = False
                for p2 in players[i+1:]:
                    if p2 not in used:
                        if tuple(sorted([p1, p2])) in played_pairs:
                            continue  # already faced, skip
                        pairings.append((p1, p2))
                        used.add(p1)
                        used.add(p2)
                        found_opponent = True
                        break
                if not found_opponent:
                    # bye
                    pairings.append((p1, None))
                    used.add(p1)

            # Create round in DB
            new_round_id = self.db.create_round(tourney_id, next_round_number, pairings)

            # Let user reorder pairings in a drag-and-drop editor
            def after_save():
                refresh_rounds()

            editor = PairingEditor(
                master=self.root,
                db=self.db,
                round_id=new_round_id,
                initial_pairings=pairings,
                on_save_callback=after_save
            )
            editor.grab_set()  # Make the window modal if desired

        def update_results():
            sel = r_list.selection()
            if not sel:
                messagebox.showerror("Error", "No round selected")
                return

            round_id = r_list.item(sel, "values")[0]
            pairings_json = r_list.item(sel, "values")[2]
            results_json = r_list.item(sel, "values")[3]

            try:
                pairings = json.loads(pairings_json)
            except:
                pairings = []
            existing_results = []
            if results_json and results_json != "Pending":
                try:
                    existing_results = json.loads(results_json)
                except:
                    existing_results = []

            # Convert existing_results to a dict
            results_dict = {}
            for r in existing_results:
                w_id = r.get("white_id")
                b_id = r.get("black_id")
                w_pts = r.get("white_points", 0)
                b_pts = r.get("black_points", 0)
                results_dict[(w_id, b_id)] = (w_pts, b_pts)

            entries = []

            def save_results():
                new_results = []
                for (white_id, black_id, w_var, b_var) in entries:
                    try:
                        w_pts = float(w_var.get())
                        b_pts = float(b_var.get())
                    except ValueError:
                        messagebox.showerror("Error", "Points must be numeric.")
                        return

                    if white_id is not None:
                        self.db.update_player_points(white_id, tourney_id, w_pts)
                    if black_id is not None:
                        self.db.update_player_points(black_id, tourney_id, b_pts)

                    new_results.append({
                        "white_id": white_id,
                        "black_id": black_id,
                        "white_points": w_pts,
                        "black_points": b_pts
                    })

                self.db.update_round_results(round_id, new_results)
                refresh_rounds()
                result_window.destroy()

            result_window = Toplevel(self.root)
            result_window.title("Update Results")

            for i, (white_id, black_id) in enumerate(pairings):
                w_name = self.db.get_player_name(white_id) if white_id else "Bye"
                b_name = self.db.get_player_name(black_id) if black_id else "Bye"

                tk.Label(result_window, text=f"{w_name} vs {b_name}").grid(row=i, column=0, padx=10, pady=5)

                old_w_pts, old_b_pts = results_dict.get((white_id, black_id), (0.0, 0.0))
                w_var = tk.StringVar(value=str(old_w_pts))
                b_var = tk.StringVar(value=str(old_b_pts))

                tk.Entry(result_window, textvariable=w_var, width=5).grid(row=i, column=1, padx=5)
                tk.Label(result_window, text="-").grid(row=i, column=2, padx=5)
                tk.Entry(result_window, textvariable=b_var, width=5).grid(row=i, column=3, padx=5)

                entries.append((white_id, black_id, w_var, b_var))

            tk.Button(result_window, text="Save Results", command=save_results).grid(
                row=len(pairings) + 1, column=0, columnspan=4, pady=10
            )

        def view_results():
            sel = r_list.selection()
            if not sel:
                messagebox.showerror("Error", "No round selected")
                return
            round_id = r_list.item(sel, "values")[0]
            results_json = r_list.item(sel, "values")[3]
            if not results_json or results_json == "Pending":
                messagebox.showinfo("Results", "No results available yet.")
                return

            results_data = json.loads(results_json)

            result_window = Toplevel(self.root)
            result_window.title(f"Results - Round {round_id}")

            for i, res in enumerate(results_data):
                w_id = res["white_id"]
                b_id = res["black_id"]
                w_pts = res["white_points"]
                b_pts = res["black_points"]

                w_name = self.db.get_player_name(w_id) if w_id else "Bye"
                b_name = self.db.get_player_name(b_id) if b_id else "Bye"

                tk.Label(result_window, text=f"{w_name} ({w_pts}) vs {b_name} ({b_pts})").grid(
                    row=i, column=0, padx=10, pady=5
                )

        ctrl = tk.Frame(frame)
        ctrl.pack(pady=10)
        tk.Button(ctrl, text="Generate Round", command=generate_round).grid(row=0, column=0, padx=5)
        tk.Button(ctrl, text="Update Results", command=update_results).grid(row=0, column=1, padx=5)
        tk.Button(ctrl, text="View Results", command=view_results).grid(row=0, column=2, padx=5)

        refresh_rounds()

    # ----------------------------------------------------------------
    #                       Standings Tab
    # ----------------------------------------------------------------

    def build_standings_tab(self, notebook: Notebook, tourney_id: int) -> None:
        frame = tk.Frame(notebook)
        notebook.add(frame, text="Standings")

        tk.Label(frame, text="Standings", font=("Arial", 12, "bold")).pack(pady=5)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        standings_list = Treeview(
            tree_frame,
            columns=("Rank", "Player", "Points", "Buchholz", "Wins"),
            show="headings"
        )
        standings_list.heading("Rank", text="Rank")
        standings_list.heading("Player", text="Player")
        standings_list.heading("Points", text="Points")
        standings_list.heading("Buchholz", text="Buchholz")
        standings_list.heading("Wins", text="Wins")

        standings_list.column("Rank", width=50, anchor=tk.CENTER)
        standings_list.column("Player", width=180, anchor=tk.W)
        standings_list.column("Points", width=60, anchor=tk.CENTER)
        standings_list.column("Buchholz", width=80, anchor=tk.CENTER)
        standings_list.column("Wins", width=60, anchor=tk.CENTER)

        scroll_y = Scrollbar(tree_frame, orient="vertical", command=standings_list.yview)
        standings_list.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        standings_list.pack(side="left", fill="both", expand=True)

        def refresh_standings():
            standings_list.delete(*standings_list.get_children())

            # 1) All players + base points
            players_info = self.db.get_all_players_with_points(tourney_id)
            players_dict = {}
            for pid, pname, pts in players_info:
                players_dict[pid] = {
                    "name": pname,
                    "points": pts,
                    "wins": 0,
                    "buchholz": 0,
                    "opponents": set()
                }

            # 2) For each round, parse pairings/results
            rounds_data = self.db.get_rounds_for_tournament(tourney_id)
            for (round_id, round_number, pairings_json, results_json) in rounds_data:
                try:
                    pairings = json.loads(pairings_json)
                except:
                    pairings = []
                if not results_json or results_json == "Pending":
                    continue
                try:
                    results = json.loads(results_json)
                except:
                    results = []

                results_dict = {}
                for r in results:
                    w_id = r.get("white_id")
                    b_id = r.get("black_id")
                    w_pts = r.get("white_points", 0)
                    b_pts = r.get("black_points", 0)
                    results_dict[(w_id, b_id)] = (w_pts, b_pts)

                for (white_id, black_id) in pairings:
                    if white_id is None or black_id is None:
                        continue
                    if (white_id, black_id) not in results_dict:
                        continue

                    w_pts, b_pts = results_dict[(white_id, black_id)]
                    # Wins
                    if white_id in players_dict and w_pts == 1.0:
                        players_dict[white_id]["wins"] += 1
                    if black_id in players_dict and b_pts == 1.0:
                        players_dict[black_id]["wins"] += 1

                    # Opponents
                    players_dict[white_id]["opponents"].add(black_id)
                    players_dict[black_id]["opponents"].add(white_id)

            # 3) Compute Buchholz
            for pid, data in players_dict.items():
                bch = 0
                for opp_id in data["opponents"]:
                    if opp_id in players_dict:
                        bch += players_dict[opp_id]["points"]
                data["buchholz"] = bch

            # 4) Build final list
            final_list = []
            for pid, data in players_dict.items():
                final_list.append((
                    data["name"],
                    data["points"],
                    data["buchholz"],
                    data["wins"]
                ))

            final_list.sort(key=lambda x: (-x[1], -x[2], -x[3]))

            # 5) Insert
            for rank, (pname, pts, bch, wins) in enumerate(final_list, start=1):
                standings_list.insert("", "end", values=(rank, pname, pts, bch, wins))

        tk.Button(frame, text="Refresh Standings", command=refresh_standings).pack(pady=5)
        refresh_standings()


# -------------------------------------------------------------------
#                          MAIN LAUNCH
# -------------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()

    root = tk.Tk()
    app = ChessApp(root)
    root.mainloop()
