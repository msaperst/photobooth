#!/usr/bin/env python
# declare our imports
import os
from os.path import exists
import shutil
import sys
import cups

# declare our global variables
# ###photo information
numberOfPhotos = 3
photoExtension = "jpg"
logoLocation = "logo.jpg"
textColor = "white"
textBackground = "black"
# ###strip layout
photosAcross = 1
photosDown = 4
# ###images resized to
imageHeight = 600
imageWidth = 900
watermark = None
# ###spacing
spacingColor = "white"
imageSpacing = 20
# ###image locations being definate (relative)
imageQueue = "./queuedImages"
imageStore = "./storedImages"
imageBackup = "./photoStore"
storageDrive = "/media/max/NIKON\ D700/DCIM/171ND700"
printDrive = "/media/max/NIKON\ D700"


def check_photos(photos_across=photosAcross, photos_down=photosDown, number_of_photos=numberOfPhotos,
                 logo_location=logoLocation):
    if photos_across * photos_down != number_of_photos + (0 if logo_location is None else 1):
        raise ValueError(
            'Your layout does not workout. Number of photos is incorrect. Please verify your strip properties!')
    if logo_location is not None and not exists(logo_location):
        raise ValueError(
            'The provided logo does not exist. Please verify your strip properties!')


def check_user(user):
    if user != "root":
        raise UserWarning('This program must be run as the root user')


def create_folders():
    if not os.path.exists(imageQueue):
        os.makedirs(imageQueue)
    if not os.path.exists(imageStore):
        os.makedirs(imageStore)
    if not os.path.exists(imageBackup):
        os.makedirs(imageBackup)
    if not os.path.exists(os.path.join(imageStore, 'prints')):
        os.makedirs(os.path.join(imageStore, 'prints'))


def ready_to_process():
    return len(os.listdir(imageQueue)) >= 3


if __name__ == "__main__":
    import time, getpass, datetime

    imageSet = 0
    check_photos()  # sanity check for correct setup
    check_user(getpass.getuser())  # sanity check for correct user
    create_folders()  # ensure required folders exist

    # need a loop that just runs forever, and when ready_to_process we do things, then return to the loop
    while True:
        if ready_to_process():
            print('processing!!!')
        print('waiting for photos!!!')
        time.sleep(5)

    # imageSet = sum(os.path.isdir(os.path.join(imageStore, f)) for f in os.listdir(imageStore))
    # batchSet = sum(os.path.isdir(os.path.join(imageBackup, f)) for f in os.listdir(imageBackup)) + 1
    #
    # # copy and backup our photos
    # print "Copying and backing up our photos"
    # os.makedirs(os.path.join(imageBackup, "batch" + str(batchSet)))
    # os.system("cp " + storageDrive + "/* " + imageBackup + "/batch" + str(batchSet) + "/")
    # os.system("cp " + os.path.join(storageDrive, "*.JPG") + " \"" + os.path.join(imageQueue) + "/\"")
    # os.system("cp " + os.path.join(storageDrive, "*.jpg") + " \"" + os.path.join(imageQueue) + "/\"")
    # os.system("rm -rf " + os.path.join(storageDrive, "*"))
    #
    # # start processing our images
    # counter = 0;
    # workingFolder = "";
    # for filename in sorted(os.listdir(imageQueue)):
    #     if counter % numberOfPhotos == 0:
    #         workingFolder = os.path.join(imageStore, "image" + str(imageSet + counter / numberOfPhotos))
    #         os.makedirs(workingFolder)
    #     print "Copying file " + filename
    #     thisFile = os.path.join(workingFolder, filename)
    #     shutil.copyfile(os.path.join(imageQueue, filename), thisFile)
    #     print "Resizing Image " + filename
    #     newSize = str(imageWidth) + "x" + str(imageHeight)
    #     os.system("convert -sample " + newSize + " " + thisFile + " " + thisFile)
    #     if watermark is not None:  # if we need to add our watermark
    #         print "    Adding Watermark"
    #         newImageHeight = os.system("identify -format \"%h\" " + imageQueue + "/image" + str(i) + ".jpg ")
    #         newImageHeight.rstrip("\n\r")
    #         newImageWidth = os.system("identify -format \"%w\" " + imageQueue + "/image" + str(i) + ".jpg ")
    #         newImageWidth.rstrip("\n\r")
    #         tempCorner0 = 5;
    #         tempCorner1 = newImageHeight - 17;
    #         tempCorner2 = newImageWidth - 5;
    #         tempCorner3 = newImageHeight - 5;
    #         textStartHeight = (tempCorner1 + tempCorner3) / 2 + 4;
    #         textStartWidth = (tempCorner0 + tempCorner2) / 2 - 65;
    #         os.system("convert -fill " + textBackground + " -draw 'rountRectangle " + str(tempCorner0) + "," + str(
    #             tempCorner1) + " " + str(tempCorner2) + "," + str(
    #             tempCorner3) + " 2,2' " + thisFile + " " + imageQueue + "/image" + str(i) + ".jpg")
    #         os.system("convert -font Helvetica -fill " + textColor + " -pointsize 10 -draw 'text " + str(
    #             textStartWidth) + "," + str(
    #             textStartHeight) + " \"" + watermark + "\"' " + thisFile + " " + thisFile)
    #     counter += 1
    #     if counter % numberOfPhotos == 0:  # build our strip
    #         print "Building the Strip"
    #         tile = str(photosAcross) + "x" + str(photosDown)
    #         imageString = ""
    #         newFile = os.path.join(workingFolder, "Strip.jpg")
    #         for filename in sorted(os.listdir(workingFolder)):
    #             imageString += " " + os.path.join(workingFolder, filename)
    #         if weddingLogo == 1:
    #             imageString += " " + logoLocation
    #         print "montage -tile " + tile + " -geometry " + newSize + "\>+" + str(imageSpacing) + "+" + str(
    #             imageSpacing) + " -background " + spacingColor + " " + imageString + " " + newFile
    #         os.system("montage -tile " + tile + " -geometry " + newSize + "\>+" + str(imageSpacing) + "+" + str(
    #             imageSpacing) + " -background " + spacingColor + " " + imageString + " " + newFile)
    #         os.chmod(newFile, 0777)
    #         print "Created 'Strip.jpg' in " + workingFolder
    #         # create our printable image
    #         print "Starting Creation of Printable Image"
    #         newImage = os.path.join(workingFolder, "Print" + str(imageSet + counter / numberOfPhotos - 1) + ".jpg")
    #         os.system("convert " + newFile + " -rotate 90 " + newImage)
    #         os.system(
    #             "montage -tile 1x2 -border 0 -mode concatenate -background " + spacingColor + " " + newImage + " " + newImage + " " + newImage)
    #         os.system("convert " + newImage + " -border 110x110 -bordercolor " + spacingColor + " " + newImage)
    #         os.chmod(newImage, 0777)
    #         os.system("cp " + newImage + " " + os.path.join(imageStore, "prints/"))
    #         print "Created prinable image " + newImage
    #
    # # cleanup and prep for print
    # os.system("sudo chmod -R 777 *")
    # os.system("sudo rm -rf " + os.path.join(imageQueue, '*'))
    # # check for our selphy printer
    # conn = cups.Connection()
    # printers = conn.getPrinters()
    # isSelphy = False
    # for printer in printers:
    #     if printer == "Canon-ES30":
    #         isSelphy = True
    #         break
    # if isSelphy:
    #     for filename in os.listdir(os.path.join(imageStore, 'prints')):
    #         print "Printing file " + os.path.join(imageStore, 'prints', filename)
    #         conn.printFile("Canon-ES30", os.path.join(imageStore, 'prints', filename), "Image " + filename, {})
    # else:
    #     os.system("sudo rm -rf " + os.path.join(printDrive, '*'))
    #     os.system("sudo cp " + os.path.join(imageStore, 'prints', '*') + " " + printDrive + "/")
    # # cleanup when we're done
    # os.system("sudo rm -rf " + os.path.join(imageStore, 'prints', "*"))
