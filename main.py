import os
import time
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, ListView, ListItem, Label, ProgressBar, Static, DataTable
from textual import work
from textual.binding import Binding

# Load environment variables
load_dotenv()

# Scopes needed for the app
SCOPE = "user-read-playback-state user-modify-playback-state playlist-read-private"

class PlaybackBar(Static):
    """Displays current song info and progress."""
    
    def compose(self) -> ComposeResult:
        yield Label("Not Playing", id="track_info")
        yield ProgressBar(total=100, show_eta=False, id="progress_bar")

    def update_status(self, track_name, artist_name, progress_ms, duration_ms):
        """Updates the label and progress bar."""
        self.query_one("#track_info", Label).update(f"🎵 {track_name} - {artist_name}")
        bar = self.query_one("#progress_bar", ProgressBar)
        bar.total = duration_ms
        bar.progress = progress_ms

class SpotifyTUI(App):
    """A Textual app to control Spotify."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #sidebar {
        dock: left;
        width: 30;
        height: 100%;
        border-right: solid $accent;
    }
    #main_view {
        height: 100%;
        border: solid $secondary;
    }
    PlaybackBar {
        dock: bottom;
        height: 4;
        border-top: solid $success;
        padding: 1;
    }
    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Prev"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        # Initialize Spotipy
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))
        self.playlists = []
        self.current_playlist_tracks = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Vertical(
                Label("[b]My Playlists[/b]", classes="header"),
                ListView(id="playlist_list"), 
                id="sidebar"
            ),
            Vertical(
                DataTable(id="track_table"), 
                id="main_view"
            ),
        )
        yield PlaybackBar()
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app starts."""
        self.setup_ui()
        self.set_interval(1, self.update_playback_state)  # Poll Spotify every second

    @work(exclusive=True)
    async def setup_ui(self):
        """Fetches playlists and populates the sidebar."""
        try:
            results = self.sp.current_user_playlists(limit=20)
            self.playlists = results['items']
            
            list_view = self.query_one("#playlist_list", ListView)
            for pl in self.playlists:
                list_view.append(ListItem(Label(pl['name'])))
            
            # Setup Track Table columns
            table = self.query_one("#track_table", DataTable)
            table.cursor_type = "row"
            table.add_columns("Title", "Artist", "Album")
            
        except Exception as e:
            self.notify(f"Error loading playlists: {e}", severity="error")

    async def on_list_view_selected(self, message: ListView.Selected):
        """Handle playlist selection."""
        # Find which playlist was clicked based on index
        if message.list_view.id == "playlist_list":
            index = message.list_view.index
            if index is not None and index < len(self.playlists):
                selected_playlist = self.playlists[index]
                self.load_tracks(selected_playlist['id'])

    @work(exclusive=True)
    async def load_tracks(self, playlist_id):
        """Fetches tracks for a playlist and updates the main table."""
        try:
            results = self.sp.playlist_items(playlist_id, limit=50)
            tracks = results['items']
            self.current_playlist_tracks = tracks
            
            table = self.query_one("#track_table", DataTable)
            table.clear()
            
            for item in tracks:
                track = item['track']
                if track:
                    table.add_row(
                        track['name'], 
                        ", ".join(artist['name'] for artist in track['artists']),
                        track['album']['name']
                    )
            table.focus() # Move focus to tracks so user can hit enter to play
            
        except Exception as e:
            self.notify(f"Error loading tracks: {e}", severity="error")

    async def on_data_table_row_selected(self, message: DataTable.RowSelected):
        """Handle track selection to play music."""
        try:
            row_index = message.cursor_row
            track_uri = self.current_playlist_tracks[row_index]['track']['uri']
            
            # Start playback (Requires an active device)
            self.sp.start_playback(uris=[track_uri])
            self.notify("Playback started!")
            self.update_playback_state() # Immediate update
            
        except spotipy.SpotifyException as e:
            self.notify("Ensure Spotify is open on a device!", severity="error")

    def update_playback_state(self):
        """Polls Spotify for current playback status."""
        try:
            current = self.sp.current_playback()
            if current and current['is_playing']:
                item = current['item']
                progress = current['progress_ms']
                duration = item['duration_ms']
                
                bar = self.query_one(PlaybackBar)
                bar.update_status(
                    item['name'], 
                    item['artists'][0]['name'], 
                    progress, 
                    duration
                )
        except:
            pass # Fail silently on network blips

    # --- Controls ---
    def action_toggle_play(self):
        try:
            current = self.sp.current_playback()
            if current and current['is_playing']:
                self.sp.pause_playback()
            else:
                self.sp.start_playback()
        except: pass

    def action_next_track(self):
        try: self.sp.next_track() 
        except: pass

    def action_prev_track(self):
        try: self.sp.previous_track() 
        except: pass

if __name__ == "__main__":
    app = SpotifyTUI()
    app.run()