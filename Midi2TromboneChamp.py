import mido.midifiles as mido
from mido import MidiFile, MetaMessage
import pyperclip


import sys
import json
import random
from easygui import *
import os
import math
import sys


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

if __name__ == '__main__':

    nyxTracks = dict()
    for i in range(16):
        nyxTracks[i] = []
    # Import the MIDI file...
    mid = MidiFile(filename=path, clip=True)

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
    defaultLength = 0.2
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

                
                
                if (message.type == "note_on"):
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
                                currentNote[1] = defaultLength
                        
                        notes += [currentNote]
                        currentNote = SetupNote(currBeat, 0, noteToUse, noteToUse)
                    print(currentNote)
                    noteHeld = True

                    
                if (message.type == "note_off"):
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
                                currentNote[1] = defaultLength
                            #print(currentNote)
                            notes += [currentNote]
                            noteHeld = False


        final_bar = max(final_bar, currBeat)
        #print("totaltime: " + str(totaltime)+"s")

            
    notes = sorted(notes, key=lambda x: x[0] )   
    pyperclip.copy(str(notes))
    
    msg = "Enter the Chart Info"
    title = "Chart Info"
    
    fieldNames = ["Song Name","Short Name", "Folder Name", "Year","Author", "Genre", "Description", "Difficulty", "Note Spacing", "Song Endpoint (in beats)", "Beats per Bar"]
    fieldValues = [songName, songName, songName.replace(" ",""), "2022", "", "","", "5", "120", int(final_bar+4), 2]  # we start with blanks for the values
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

    if (True):

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
        dicc["lyrics"]= []
        dicc["UNK1"]= 0

    json = json.dumps(dicc)

    out = filesavebox(default="song"+'.tmb')
    with open(out,"w") as file:
        file.write(json)


sys.exit()
