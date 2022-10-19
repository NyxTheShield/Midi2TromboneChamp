from mido import MidiFile, MetaMessage
import pyperclip

import sys
import json
from easygui import *
import os
import math
from collections import OrderedDict


DEFAULT_TEMPO = 0.5
DEFAULT_NOTE_LENGTH = 0.2
APPDATA_DIR = os.path.expandvars(r'%LOCALAPPDATA%\Midi2TromboneChamp')


def resource_path():
    # https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
    # pyinstaller secretly runs application from a temp directly and doesn't pass the original exe location through,
    # so rather than creating a .json wherever the exe is, we have to dump it in appdata
    directory = APPDATA_DIR  # if getattr(sys, 'frozen', False) else os.path.dirname(os.path.realpath(__file__))
    if not os.path.exists(directory):
        print(f"Creating directory to store config: {directory}")
        os.mkdir(directory)
    return directory


def ticks2s(ticks, tempo, ticks_per_beat):
    """
        Converts ticks to seconds
    """
    return ticks/ticks_per_beat * tempo


def note2freq(x):
    """
        Convert a MIDI note into a frequency (given in Hz)
    """
    a = 440
    return (a/32) * (2 ** ((x-9)/12))


def round_decimals_up(number:float, decimals:int=2):
    """
    Returns a value rounded up to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.ceil(number)

    factor = 10 ** decimals
    return math.ceil(number * factor) / factor


def is_note_on(msg):
    return msg.type == "note_on" and msg.velocity > 0


def is_note_off(msg):
    return msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)


def SetupNote(beat, length, noteNumber, endNoteNumber):
    startPitch = (noteNumber-60)*13.75
    endPitch = (endNoteNumber-60)*13.75
    return [beat, length , startPitch , endPitch - startPitch , endPitch]


class DialogFieldValues:
    _history_file = os.path.join(resource_path(), "history.json")

    def __init__(self):
        # Default values for each field go here
        self.open_midi_file = '*'
        # Chart info (.tmp file)
        self.song_name = ""
        self.short_name = ""
        self.directory_name = ""
        self.year = 2022
        self.artist = "Unknown"
        self.genre = "Korean Hyper Folk Emo"
        self.description = "The charter was too lazy to fill out a description. Boo the lazy charter! BOOOOO!!!"
        self.difficulty = 10
        self.spacing = 120
        # NOTE: Skipping song endpoint as that can always be inferred
        self.bpm = 120
        self.bpb = 2

        self.save_tmb_file = 'song.tmb'

        if os.path.exists(DialogFieldValues._history_file):
            try:
                self._populate_from_history()
            except:
                print("ERROR: Exception was raised when trying to load dialog history! " +
                      f"You may need to delete {DialogFieldValues._history_file} to fix. " +
                      f"If that doesn't work, ping @devook on Discord with the stack trace.")
                raise

    def _populate_from_history(self):
        with open(DialogFieldValues._history_file, "r") as f:
            history = json.load(f)
        for key, value in history.items():
            if key not in self.__dict__:
                print(f"{key}: {history[key]} removed because DialogFields doesn't have this field any more")
                continue
            self.__dict__[key] = history[key]

    def populate_empty_names(self, song_name):
        if self.song_name.strip() == "":
            self.song_name = song_name
            self.short_name = song_name
        if self.directory_name.strip() == "":
            self.directory_name = song_name

    def get_multi_field_mappings(self) -> OrderedDict:
        """
        Provides the definitive mapping between what the fields are named in the multi-enter box prompt, and
        which attributes those field names map to in the DialogFieldValues class. Defined here because I hate using
        parallel-indexed lists as a standin for a hashmap-like structure, but those structures are forced on us
        by easygui.multenterbox
        """
        fields = OrderedDict()
        fields["Song Name"] = "song_name"
        fields["Short Name"] = "short_name"
        fields["Folder Name"] = "directory_name"
        fields["Year"] = "year"
        fields["Author"] = "artist"
        fields["Genre"] = "genre"
        fields["Description"] = "description"
        fields["Difficulty"] = "difficulty"
        fields["Note Spacing"] = "spacing"
        fields["Beats Per Bar"] = "bpb"
        # TODO: This should be a unit test, really...
        assert all(hasattr(self, name) for name in fields.values()), \
            f"Field names in {self.get_multi_field_mappings.__name__} are out-dated: " \
            f"{[name for name in fields.values() if not hasattr(self, name)]} are not attributes of {DialogFieldValues.__name__}"
        return fields

    # TODO: Fields should be sanitized before being stored so we don't need to do any type-casting here
    def to_chart_info(self, endpoint) -> dict:
        return {
            "name": self.song_name,
            "shortName": self.short_name,
            "trackRef": self.directory_name,
            "year": int(self.year),
            "author": self.artist,
            "genre": self.genre,
            "description": self.description,
            "difficulty": int(self.difficulty),
            "savednotespacing": int(self.spacing),
            "endpoint": endpoint,
            "timesig": int(self.bpb),
            "tempo": int(self.bpm),
            # TODO: Add support for lyrics (probably needs work on TrombLoader side too)
            "lyrics": [],
            "UNK1": 0
        }
        # info["name"] = fieldValues[0]
        # info["shortName"] = fieldValues[1]
        # info["trackRef"] = fieldValues[2]
        # info["year"] = int(fieldValues[3])
        # info["author"] = fieldValues[4]
        # info["genre"] = fieldValues[5]
        # info["description"] = fieldValues[6]
        # info["difficulty"] = int(fieldValues[7])
        # info["savednotespacing"] = int(fieldValues[8])
        # info["endpoint"] = int(fieldValues[9])
        # info["timesig"] = int(fieldValues[10])
        # info["tempo"] = int(bpm)
        # info["lyrics"] = []
        # info["UNK1"] = 0

    def save(self):
        with open(DialogFieldValues._history_file, "w") as f:
            json.dump(self.__dict__, f)


class DialogBoxes:

    def __init__(self):
        self.__values = DialogFieldValues()

    @staticmethod
    def _default_if_none(possibly_none, default_value):
        return default_value if possibly_none is None else possibly_none

    @staticmethod
    def _default_if_path_not_exists(possible_path, default_value):
        return possible_path if possible_path is not None and os.path.exists(possible_path) else default_value

    def _quit_or_save(self, value):
        if value is None:
            print("Got None back from a dialog -- assuming we canceled and quitting!")
            quit(1)
        self.__values.save()
        return value

    # TODO? Might want to revisit and make the validation a little more robust
    # Difficulty, for example is only valid on a scale of 0-10, date should be a YYYY-formatted year, etc.
    def _is_chart_info_valid(self, mapping, fields, values):
        return all(v.strip() != "" for v in values)

    def prompt_for_midi_file(self):
        default_path = DialogBoxes._default_if_path_not_exists(self.__values.open_midi_file, '*')
        self.__values.open_midi_file = fileopenbox(
            msg="Choose a MIDI file to convert.",
            default=default_path,
            filetypes=[["\\*.mid", "\\*.midi"], "MIDI files"])
        return self._quit_or_save(self.__values.open_midi_file)

    def prompt_for_bpm(self):
        # NOTE: Truncating to int in text box here,
        # although users are free to give float values if they really want to...
        bpm = enterbox("BPM of Midi", "Enter BPM", "{:.0f}".format(self.__values.bpm))
        # float(None) will throw an exception, so have to go around it when dialog is canceled
        self.__values.bpm = None if bpm is None else float(bpm)
        return self._quit_or_save(self.__values.bpm)

    def prompt_for_chart_info(self, song_name, final_bar):
        msg = "Enter the Chart Info"
        title = "Chart Info"
        self.__values.populate_empty_names(song_name)
        field_mappings = self.__values.get_multi_field_mappings()
        # We don't save a value for Endpoint because it can be inferred and is likely to change between iterations
        field_names = list(field_mappings.keys()) + ["Song Endpoint (in beats)"]
        field_values = [getattr(self.__values, name) for name in field_mappings.values()] + [int(final_bar + 4)]
        all_fields_ok = False
        while not all_fields_ok:
            field_values = multenterbox(msg, title, field_names, field_values)
            if field_values is None:
                print("Cancel pressed -- quitting")
                quit(1)
            all_fields_ok = self._is_chart_info_valid(field_mappings, field_names, field_values)
            # If we loop around, we'll use this message instead
            msg = "All fields are required. Please don't leave any blank."

        # Push new values back into history for everything we're keeping track of (not song endpoint)
        for name, value in zip(field_names, field_values):
            if name in field_mappings:
                setattr(self.__values, field_mappings[name], value)
        self.__values.save()

        # TODO: Remove this assumption that final_bar is always the last entry in the values array
        return self.__values.to_chart_info(int(field_values[-1]))

    def prompt_for_file_save(self):
        self.__values.save_tmb_file = filesavebox(default=self.__values.save_tmb_file)
        return self._quit_or_save(self.__values.save_tmb_file)


if __name__ == '__main__':
    dialog = DialogBoxes()
    midi_file = dialog.prompt_for_midi_file()
    song_name = os.path.splitext(os.path.basename(midi_file))[0]
    bpm = dialog.prompt_for_bpm()
    nyxTracks = dict()
    for i in range(16):
        nyxTracks[i] = []
    # Import the MIDI file...
    mid = MidiFile(filename=midi_file, clip=True)

    print("TYPE: " + str(mid.type))
    print("LENGTH: " + str(mid.length))
    print("TICKS PER BEAT: " + str(mid.ticks_per_beat))

    if mid.type == 3:
        print("Unsupported type.")
        exit()

    """
        First read all the notes in the MIDI file
    """
    tracksMerged = []
    notes = {}
    tick_duration = 60/(mid.ticks_per_beat*bpm)
    
    notes = []
    print("Tick Duration:")
    print(tick_duration)

    print("Tempo:" + str(DEFAULT_TEMPO))
        
    final_bar = 0

    allMidiEventsSorted = []

    for i, track in enumerate(mid.tracks):
        currTrack = i
        tempo = DEFAULT_TEMPO
        totaltime = 0
        globalTime = 0
        currentNote = []
        globalBeatTime = 0
        currBeat = 0
        for message in track:
            t = ticks2s(message.time, tempo, mid.ticks_per_beat)
            tromboneBeat = message.time/mid.ticks_per_beat
            totaltime += t

            if isinstance(message, MetaMessage):  # Tempo change
                if message.type == "set_tempo":
                    tempo = message.tempo / 10**6
                elif message.type == "end_of_track":
                    pass
                else:
                    print("Unsupported metamessage: " + str(message))

            else:
                globalTime+= message.time
                globalBeatTime+= tromboneBeat
                    
                currTime = globalTime*tick_duration*1000
                currBeat = round(globalBeatTime,3)
                allMidiEventsSorted += [(i,message, currBeat)]


    
    allMidiEventsSorted = sorted(allMidiEventsSorted, key=lambda x: x[2] )

    keyframes = []
    for i, message, currBeat in allMidiEventsSorted:
        if message.type == "note_on":
            seconds = currBeat*60/bpm
            keyframes += [(seconds, (message.note -60)/12)]
                    
    currTrack = i
    tempo = DEFAULT_TEMPO
    totaltime = 0
    globalTime = 0
    currentNote = []
    globalBeatTime = 0
    noteToUse = 0
    lastNote = -1000
    lastChannel = -1
    DEFAULT_NOTE_LENGTH = 0.2
    noteTrimming = 0.0
    currBeat = 0
    noteHeld = False
    
    for i, message, currBeat in allMidiEventsSorted:
        if (True):
            if isinstance(message, MetaMessage):  # Tempo change
                if message.type == "set_tempo":
                    tempo = message.tempo / 10**6
                elif message.type == "end_of_track":
                    pass
                else:
                    print("Unsupported metamessage: " + str(message))

            else:  # Note
                if is_note_on(message):
                    noteToUse = min(max(48, message.note),72)
                    lastNote = noteToUse
                    lastChannel = message.channel
                    if (not noteHeld):
                        #No notes being held, so we set it up
                        currentNote = SetupNote(currBeat, 0, noteToUse, noteToUse)
                    else:
                        #If we are holding one, we add the previous note we set up, and set up a new one
                        print("Cancelling Previous note!" + str(currBeat) + " old is" + str(currentNote[0]))
                        currentNote[1] = round(currBeat-currentNote[0],3)
                        currentNote[4] = (noteToUse-60)*13.75
                        currentNote[3] = currentNote[4]-currentNote[2]

                        for noteParam in range(len(currentNote)):
                                currentNote[noteParam] = round(currentNote[noteParam],3)
                        if (currentNote[1] == 0):
                                currentNote[1] = DEFAULT_NOTE_LENGTH
                        
                        notes += [currentNote]
                        currentNote = SetupNote(currBeat, 0, noteToUse, noteToUse)
                    print(currentNote)
                    noteHeld = True

                if is_note_off(message):
                    noteToUse = min(max(48, message.note),72)
                    if (message.channel == 1):
                        print("Skipping channel 1 note off...")
                    if (message.channel == 0):
                        if (noteToUse == lastNote and noteHeld):
                            currentNote[1] = round(currBeat-currentNote[0] - noteTrimming,3)
                            currentNote[4] = currentNote[4]
                            currentNote[3] = 0

                            for noteParam in range(len(currentNote)):
                                currentNote[noteParam] = round(currentNote[noteParam],3)

                            if (currentNote[1] <= 0):
                                currentNote[1] = DEFAULT_NOTE_LENGTH
                            #print(currentNote)
                            notes += [currentNote]
                            noteHeld = False


        final_bar = max(final_bar, currBeat)
        #print("totaltime: " + str(totaltime)+"s")
            
    notes = sorted(notes, key=lambda x: x[0] )
    pyperclip.copy(str(notes))

    chart_info = dialog.prompt_for_chart_info(song_name, final_bar)
    chart_info["notes"] = notes

    out = dialog.prompt_for_file_save()
    with open(out, "w") as f:
        json.dump(chart_info, f)

sys.exit()
