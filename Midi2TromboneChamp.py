import mido.midifiles as mido
from mido import MidiFile, MetaMessage, MidiTrack

import sys
import json
from easygui import *
import os
import math
import sys

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

def SetupNote(beat, length, noteNumber, endNoteNumber):
    startPitch = (noteNumber-60)*13.75
    endPitch = (endNoteNumber-60)*13.75
    return [beat, length , startPitch , endPitch - startPitch , endPitch]

# Substitute lyrics with stuff
def subLyrics(lyric):
    l = lyric.replace("=","-")
    l = l.replace("+","")
    l = l.replace("#","")
    l = l.replace("^","")
    l = l.replace("`",'"')
    return l

def history_file_path():
    # https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
    # pyinstaller secretly runs application from a temp directly and doesn't pass the original exe location through,
    # so rather than creating a .json wherever the exe is, we have to dump it in appdata
    directory = os.path.expandvars(r'%LOCALAPPDATA%\Midi2TromboneChamp')
    if not os.path.exists(directory):
        print(f"Creating directory to store config: {directory}")
        os.mkdir(directory)
    return os.path.join(directory, "history.json")

# Load the field history
dicc = dict()
fileHistory = dict()
history_file = history_file_path()
loadSuccess = False
if os.path.exists(history_file):
    try:
        with open(history_file, "r") as f:
            fileHistory = json.load(f)
        loadSuccess = True
        dicc["name"]= fileHistory["name"]
        dicc["shortName"]= fileHistory["shortName"]
        dicc["trackRef"]= fileHistory["trackRef"]
        dicc["year"] = fileHistory["year"]
        dicc["author"] = fileHistory["author"]
        dicc["genre"] = fileHistory["genre"]
        dicc["description"] = fileHistory["description"]
        dicc["difficulty"] = fileHistory["difficulty"]
        dicc["savednotespacing"] = fileHistory["savednotespacing"]
        dicc["timesig"] = fileHistory["timesig"]
    except:
        print("ERROR: Exception was raised when trying to load dialog history! " +
              f"You may need to delete {history_file} to fix. Ignoring the history for now")
if not loadSuccess:
    # Default values for first time loading or if error occurred
    dicc["name"]= ""
    dicc["shortName"]= ""
    dicc["trackRef"]= ""
    dicc["year"] = 2022
    dicc["author"] = ""
    dicc["genre"] = ""
    dicc["description"] = ""
    dicc["difficulty"] = 5
    dicc["savednotespacing"] = 120
    dicc["timesig"] = 4
    fileHistory["midfile"] = "*"
    fileHistory["savefile"] = "song.tmb"

path = fileopenbox(msg="Choose a MIDI file to convert.",
                    default=fileHistory["midfile"],
                    filetypes=[["\\*.mid", "\\*.midi"], "MIDI files"])
fileHistory["midfile"] = path
filename = os.path.basename(path)
filename = os.path.splitext(filename)[0]
songName = filename
shortName = songName
trackRef = songName.replace(" ","")
defaultLength = 0.2
bpm = float(enterbox("BPM of Midi", "Enter BPM", 120))
DEFAULT_TEMPO = 60 / bpm

# Compensation for the fact that TromboneChamp doesn't change tempo
# These tempo values are in seconds per beat except bpm what and why
def DynamicBeatToTromboneBeat(tempoEvents, midiBeat):
    baseTempo = 60 / bpm
    idx = 0
    if tempoEvents[0][1] == 0:
        baseTempo = tempoEvents[0][0]
        idx = 1
    previousMark = 0
    time = 0
    for i in range(idx,len(tempoEvents) + 1):
        if i < len(tempoEvents) and midiBeat >= tempoEvents[i][1]:
            time += baseTempo * (tempoEvents[i][1] - previousMark)
            previousMark = tempoEvents[i][1]
            baseTempo = tempoEvents[i][0]
        else:
            time += baseTempo * (midiBeat - previousMark)
            break
    return round((time * bpm) / 60, 3)

if __name__ == '__main__':
    # Import the MIDI file...
    mid = MidiFile(path, clip=True)

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
    tempoEvents = []
    lyricEvents = []
    skipOtherTracks = False

    for i, track in enumerate(mid.tracks):
        tempo = DEFAULT_TEMPO
        totaltime = 0
        globalTime = 0
        currentNote = []
        glissyHints = dict()
        globalBeatTime = 0
        for message in track:
            t = ticks2s(message.time, tempo, mid.ticks_per_beat)
            tromboneBeat = message.time/mid.ticks_per_beat
            totaltime += t
            globalTime+= message.time
            globalBeatTime+= tromboneBeat
            currTime = globalTime*tick_duration*1000

            if isinstance(message, MetaMessage):
                if message.type == "set_tempo":
                    # Tempo change
                    tempo = message.tempo / 10**6
                    tempoEvents += [(tempo, globalBeatTime)]
                    print("Tempo Event: " + str(tempo) + " spb | " + str(globalBeatTime))
                elif message.type == "track_name":
                    if (message.name in ["PART VOCALS", "PART_VOCALS", "BAND VOCALS", "BAND_VOCALS"]):
                        # Special track label for rockband/guitar hero tracks. All other events void.
                        allMidiEventsSorted = []
                        glissyHints = {}
                        # Nothing important should be skipped, first track should be tempo and stuff
                        skipOtherTracks = True
                elif message.type == "lyrics" or message.type == "text":
                    if message.text[0] == "[":
                        continue
                    if message.text == "+":
                        # Used in RB to hint that notes are slurred together
                        glissyHints[globalBeatTime] = None
                    else:
                        lyricEvents += [(i, message.text, DynamicBeatToTromboneBeat(tempoEvents, globalBeatTime))]
                elif message.type == "end_of_track":
                    pass
                else:
                    print("Unsupported metamessage: " + str(message))

            else:
                allMidiEventsSorted += [(i, message, globalBeatTime)]
        if skipOtherTracks:
            break

    allMidiEventsSorted = sorted(allMidiEventsSorted, key=lambda x: x[2] )

    # Sort out lyric events
    lyricsOut = []
    for i, lyric, beat in lyricEvents:
        l = subLyrics(lyric)
        if l == "":
            continue
        lyricEvent = dict()
        lyricEvent["text"] = l
        lyricEvent["bar"] = round(beat, 3)
        lyricsOut += [lyricEvent]

    tempo = DEFAULT_TEMPO
    totaltime = 0
    globalTime = 0
    currentNote = []
    globalBeatTime = 0
    noteToUse = 0
    lastNote = -1000
    defaultLength = 0.2
    defaultSpacing = 0.2
    noteTrimming = 0.0
    currBeat = 0
    noteHeld = False
    lastNoteOffBeat = 0
    heldNoteChannel = -1

    for i, message, currBeat in allMidiEventsSorted:
        currentBeat2 = DynamicBeatToTromboneBeat(tempoEvents, currBeat)
        if isinstance(message, MetaMessage):
            if message.type == "end_of_track":
                pass
            else:
                print("Unsupported metamessage: " + str(message))
        else:  # Note
            if (message.type in ["note_on", "note_off"] and (message.note >= 96 or message.note < 16)):
                # ignore these special control signals for stuff like phrase start and end
                continue
            if (message.type == "note_on" and message.velocity > 0):
                noteToUse = min(max(48, message.note),72)
                lastNote = noteToUse
                if (lastNoteOffBeat == currentBeat2): noteHeld = True
                try:
                    glissyHints[currBeat]
                    noteHeld = True
                except:
                    pass
                # Truncate previous note if this next note is a little too close
                try:
                    spacing = currentBeat2 - (notes[-1][1] + notes[-1][0])
                    if (not noteHeld and spacing < defaultSpacing):
                        notes[-1][1] = round(min(max(defaultLength, notes[-1][1] - (defaultSpacing - spacing)), notes[-1][1]), 3)
                except:
                    pass
                if (not noteHeld):
                    #No notes being held, so we set it up
                    currentNote = SetupNote(currentBeat2, 0, noteToUse, noteToUse)
                    heldNoteChannel = message.channel
                else:
                    #If we are holding one, we add the previous note we set up, and set up a new one
                    print("Cancelling Previous note! " + str(currentBeat2) + " old is " + str(currentNote[0]))
                    # if currentNote has a length, that means that the previous note was already terminated
                    # and this is a special condition to force a glissando
                    if (currentNote[1] > defaultLength * 2):
                        notes.pop()
                        # it looks better if the slide starts in the middle of the previous note
                        # but this isn't always best if the note is too short
                        currentNote[1] = round(max(defaultLength,currentNote[1] / 2),3)
                        notes += [currentNote]
                        currentNote = [round(currentNote[0] + currentNote[1], 3),0,currentNote[2],0,0]
                    elif (currentNote[1] > 0):
                        # remove previous note, new note becomes a slide
                        notes.pop()
                    currentNote[1] = round(currentBeat2-currentNote[0],3)
                    currentNote[4] = (noteToUse-60)*13.75
                    currentNote[3] = currentNote[4]-currentNote[2]

                    for noteParam in range(len(currentNote)):
                            currentNote[noteParam] = round(currentNote[noteParam],3)
                    if (currentNote[1] == 0):
                            currentNote[1] = defaultLength
                    notes += [currentNote]
                    currentNote = SetupNote(currentBeat2, 0, noteToUse, noteToUse)
                print(currentNote)
                noteHeld = True

            if (message.type == "note_off" or (message.type == "note_on" and message.velocity == 0)):
                noteToUse = min(max(48, message.note),72)
                lastNoteOffBeat = currentBeat2
                # The original intention was to terminate the held note when there was a noteoff event on channel 0
                # Other channels could be used for adding glissando. The issue is rock band charts frequently use
                # channel 3. As a compromise, note is terminated when a noteoff on the original channel is found.
                # This allows both to function as intended. And perhaps some people who accidentally use channel 1
                # will have a bit less of a headache
                if (message.channel == heldNoteChannel and noteToUse == lastNote and noteHeld):
                    currentNote[1] = round(currentBeat2-currentNote[0] - noteTrimming,3)
                    currentNote[4] = currentNote[4]
                    currentNote[3] = 0
                    for noteParam in range(len(currentNote)):
                        currentNote[noteParam] = round(currentNote[noteParam],3)
                    if (currentNote[1] <= 0):
                        currentNote[1] = defaultLength
                    #print(currentNote)
                    notes += [currentNote]
                    noteHeld = False


        final_bar = max(final_bar, currentBeat2)
        #print("totaltime: " + str(totaltime)+"s")

    notes = sorted(notes, key=lambda x: x[0] )

    msg = "Enter the Chart Info"
    title = "Chart Info"

    fieldNames =   ["Song Name",
                    "Short Name",
                    "Folder Name",
                    "Year",
                    "Author",
                    "Genre",
                    "Description",
                    "Difficulty",
                    "Note Spacing",
                    "Song Endpoint (in beats)",
                    "Beats per Bar"]
    if dicc["name"].strip() != "":
        songName = dicc["name"]
        shortName = dicc["shortName"]
        trackRef = dicc["trackRef"]
    fieldValues =  [songName,
                    shortName,
                    trackRef,
                    str(dicc["year"]),
                    dicc["author"],
                    dicc["genre"],
                    dicc["description"],
                    str(dicc["difficulty"]),
                    str(dicc["savednotespacing"]),
                    int(final_bar+4),
                    str(dicc["timesig"])]
    fieldValues = multenterbox(msg,title, fieldNames, fieldValues)

    # make sure that none of the fields was left blank
    while 1:
        if fieldValues == None: break
        errmsg = ""
        for i in range(len(fieldNames)):
          if fieldValues[i].strip() == "":
            errmsg = errmsg + ('"%s" is a required field.\n\n' % fieldNames[i])
        if errmsg == "": break # no problems found
        fieldValues = multenterbox(errmsg, title, fieldNames, fieldValues)

    dicc["name"]= fieldValues[0]
    dicc["shortName"]= fieldValues[1]
    dicc["trackRef"]= fieldValues[2]
    dicc["year"]= int(fieldValues[3])
    dicc["author"]= fieldValues[4]
    dicc["genre"]= fieldValues[5]
    dicc["description"]= fieldValues[6]
    dicc["difficulty"]= int(fieldValues[7])
    dicc["savednotespacing"]= int(fieldValues[8])
    dicc["timesig"]= int(fieldValues[10])

    settingjson = dicc.copy()
    settingjson["midfile"] = fileHistory["midfile"]
    settingjson["savefile"] = fileHistory["savefile"]

    dicc["notes"] = notes
    dicc["endpoint"]= int(fieldValues[9])
    dicc["tempo"]= int(bpm)
    dicc["lyrics"]= lyricsOut
    dicc["UNK1"]= 0

    chartjson = json.dumps(dicc)

    settingjson["savefile"] = filesavebox(default=fileHistory["savefile"])
    with open(settingjson["savefile"],"w") as file:
        file.write(chartjson)

    with open(history_file, "w") as settingFile:
        json.dump(settingjson, settingFile)

sys.exit()
