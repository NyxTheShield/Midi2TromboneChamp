import mido.midifiles as mido
from mido import MidiFile, MetaMessage, MidiTrack
import pyperclip



import sys
import json
import random
from easygui import *
import os
import math
import sys

#Monkey patch
def read_track(infile, debug=False, clip=False):
    track = MidiTrack()

    name, size = mido.midifiles.read_chunk_header(infile)

    if name != b'MTrk':
        raise IOError('no MTrk header at start of track')

    if debug:
        _dbg('-> size={}'.format(size))
        _dbg()

    start = infile.tell()
    last_status = None

    while True:
        # End of track reached.
        if infile.tell() - start == size:
            break

        if debug:
            _dbg('Message:')

        delta = mido.midifiles.read_variable_int(infile)

        if debug:
            _dbg('-> delta={}'.format(delta))

        status_byte = mido.midifiles.read_byte(infile)

        if status_byte < 0x80:
            if last_status is None:
                raise IOError('running status without last_status')
            peek_data = [status_byte]
            status_byte = last_status
        else:
            if status_byte != 0xff:
                # Meta messages don't set running status.
                last_status = status_byte
            peek_data = []

        if status_byte == 0xff:
            msg = mido.midifiles.read_meta_message(infile, delta)
        elif status_byte in [0xf0, 0xf7]:
            # TODO: I'm not quite clear on the difference between
            # f0 and f7 events.
            msg = mido.midifiles.read_sysex(infile, delta)
        else:
            msg = custom_read_message(infile, status_byte, peek_data, delta, clip)

        track.append(msg)

        if debug:
            _dbg('-> {!r}'.format(msg))
            _dbg()

    return track

#Monkey patch
def custom_read_message(infile, status_byte, peek_data, delta, clip=False):
    #print("Custom Read Message from Monkey Patch!!")
    try:
        spec = mido.midifiles.SPEC_BY_STATUS[status_byte]
    except LookupError:
        raise IOError('undefined status byte 0x{:02x}'.format(status_byte))

    # Subtract 1 for status byte.
    size = spec['length'] - 1 - len(peek_data)
    data_bytes = peek_data + mido.midifiles.read_bytes(infile, size)

    if clip:
        data_bytes = [byte if byte < 127 else 127 for byte in data_bytes]
    else:
        #All of this monkey patch just because mido fucking ends execution if it finds a byte than 127...
        for i, byte in enumerate(data_bytes):
            if byte > 127:
                data_bytes[i] = 127
                print("byte > 127?")
                #raise IOError('data byte must be in range 0..127')

    return mido.midifiles.Message.from_bytes([status_byte] + data_bytes, time=delta)

#Monkey patch
mido.midifiles.read_track = read_track

#Actual code

DEFAULT_TEMPO = 0.5

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

path = fileopenbox()
filename = os.path.basename(path)
filename = os.path.splitext(filename)[0]
songName = filename
defaultLength = 0.2
bpm = float(enterbox("BPM of Midi", "Enter BPM", 120))

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

# Substitute lyrics with stuff
def subLyrics(lyric):
    l = lyric.replace("=","-")
    l = l.replace("+","")
    l = l.replace("`",'"')
    return l

if __name__ == '__main__':
    # Import the MIDI file...
    mid = MidiFile(path)

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
        currTrack = i
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
                        # Nothing important should be skipped, first track should be tempo and stuff
                        skipOtherTracks = True
                elif message.type == "lyrics":
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
    lastLyricBeat = -10
    for i, lyric, beat in lyricEvents:
        # lyrics apparently are snapped to the nearest beat
        l = subLyrics(lyric)
        if l == "":
            continue
        if beat - lastLyricBeat <= 1:
            if lyricsOut[-1]["text"][-1] == "-":
                lyricsOut[-1]["text"] = lyricsOut[-1]["text"][:-1] + l
            else:
                lyricsOut[-1]["text"] += " " + l
        else:
            lastLyricBeat = round(beat)
            lyricEvent = dict()
            lyricEvent["text"] = l
            lyricEvent["bar"] = lastLyricBeat
            lyricsOut += [lyricEvent]

    currTrack = i
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
                        notes[-1][1] = min(max(defaultLength, notes[-1][1] - (defaultSpacing - spacing)), notes[-1][1])
                except:
                    pass
                if (not noteHeld):
                    #No notes being held, so we set it up
                    currentNote = SetupNote(currentBeat2, 0, noteToUse, noteToUse)
                else:
                    #If we are holding one, we add the previous note we set up, and set up a new one
                    print("Cancelling Previous note! " + str(currentBeat2) + " old is " + str(currentNote[0]))
                    # if currentNote has a length, that means that the previous note was already terminated
                    # and this is a special condition to force a glissando
                    if (currentNote[1] > 0): notes.pop()
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
                # if (message.channel == 1):
                #     print("Skipping channel 1 note off...")
                # if (message.channel == 0):
                # Debug, ignore channel exclusions
                if (noteToUse == lastNote and noteHeld):
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
    pyperclip.copy(str(notes))

    msg = "Enter the Chart Info"
    title = "Chart Info"

    fieldNames = ["Song Name","Short Name", "Folder Name", "Year","Author", "Genre", "Description", "Difficulty", "Note Spacing", "Song Endpoint (in beats)", "Beats per Bar"]
    fieldValues = [songName, songName, songName.replace(" ",""), "2022", "", "","", "5", "120", int(final_bar+4), 4]  # we start with blanks for the values
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

    dicc = dict()
    dicc["notes"] = notes
    dicc["name"]= fieldValues[0]
    dicc["shortName"]= fieldValues[1]
    dicc["trackRef"]= fieldValues[2]
    dicc["year"]= int(fieldValues[3])
    dicc["author"]= fieldValues[4]
    dicc["genre"]= fieldValues[5]
    dicc["description"]= fieldValues[6]
    dicc["difficulty"]= int(fieldValues[7])
    dicc["savednotespacing"]= int(fieldValues[8])
    dicc["endpoint"]= int(fieldValues[9])
    dicc["timesig"]= int(fieldValues[10])
    dicc["tempo"]= int(bpm)
    dicc["lyrics"]= lyricsOut
    dicc["UNK1"]= 0

    json = json.dumps(dicc)

    out = filesavebox(default="song"+'.tmb')
    with open(out,"w") as file:
        file.write(json)


sys.exit()
