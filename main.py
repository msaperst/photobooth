#!/usr/bin/env python
# declare our imports
import os
from os.path import exists
import gphoto2 as gp
import time, cups
from wand.image import Image

# declare our global variables
# ###photo information
numberOfPhotos = 3
photoExtension = 'jpg'
logoLocation = 'logo.jpg'
textColor = 'white'
textBackground = 'black'
# ###strip layout
photosAcross = 1
photosDown = 4
# ###images resized to
imageHeight = 600
imageWidth = 900
watermark = None
# ###spacing
spacingColor = 'white'
imageSpacing = 20
# ###image store location
imageStore = './storedImages'
# ###our camera object
camera = None


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
        raise UserWarning(f'This program must be run as the root user. You are running as {user}')


def create_folders():
    if not os.path.exists(imageStore):
        os.makedirs(imageStore)


def check_camera():
    global camera
    camera = gp.check_result(gp.gp_camera_new())
    error = gp.gp_camera_init(camera)
    if error < gp.GP_OK:
        raise UserWarning(f'No camera has been detected. Error {error} received')


def check_printer():
    conn = cups.Connection()
    printers = conn.getPrinters()
    is_selphy = False
    for printer in printers:
        if printer == "Selphy":
            is_selphy = True
            break
    if not is_selphy:
        raise UserWarning(f'No selphy printer has been detected. Only saw printers {printers}')


def list_files(path='/'):
    result = []
    # get files
    for name, value in gp.check_result(
            gp.gp_camera_folder_list_files(camera, path)):
        result.append(os.path.join(path, name))
    # read folders
    folders = []
    for name, value in gp.check_result(
            gp.gp_camera_folder_list_folders(camera, path)):
        folders.append(name)
    # recurse over subfolders
    for name in folders:
        result.extend(list_files(os.path.join(path, name)))
    return result


def ready_to_process():
    global camera
    gp.check_result(gp.gp_camera_exit(camera))
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera))
    files = list_files('/')
    return len(files) >= 6  # we're using 6, as a NEF and JPG are both created


def get_images():
    count = len(os.listdir(imageStore))
    destination_dir = os.path.join(imageStore, f'batch{count}')
    os.makedirs(destination_dir)
    files = list_files()
    for x in range(0, 6):
        # get our file information
        path = files[x]
        folder, name = os.path.split(path)
        destination = os.path.join(destination_dir, name)
        # copy the file over
        camera_file = gp.check_result(gp.gp_camera_file_get(
            camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
        gp.check_result(gp.gp_file_save(camera_file, destination))
        # remove the file
        gp.gp_camera_file_delete(camera, folder, name)
    return destination_dir


def make_print(directory):
    # get each of our files
    files = []
    files += [each for each in os.listdir(directory) if each.endswith('.JPG')]
    for file in files:
        image = Image(filename=os.path.join(directory, file))
        image.resize(imageWidth, imageHeight)
        image.save(filename=os.path.join(directory, file))
        if watermark is not None:
            raise ValueError('This functionality is not implemented yet')
            # TODO DO SOMETHING
    # build our photo strip
    tile = str(photosAcross) + "x" + str(photosDown)
    image_string = ""
    strip = os.path.join(directory, "Strip.jpg")
    new_size = str(imageWidth) + "x" + str(imageHeight)
    for filename in sorted(files):
        image_string += " " + os.path.join(directory, filename)
    if logoLocation is not None:
        image_string += " " + logoLocation
    tile_command = 'montage -tile ' + tile + ' -geometry ' + new_size + '>+' + str(imageSpacing) + '+' + str(imageSpacing) + ' -background ' + spacingColor + ' ' + image_string + ' ' + strip
    os.system(tile_command)  # NOTE - wand/pgmagick doesn't support montage, so building use system process calls
    # create our printable image
    strip_print = os.path.join(directory, "Print.jpg")
    image = Image(filename=strip)
    image.rotate(90)
    image.border(spacingColor, 20, 20)
    image.save(filename=strip_print)
    os.system("montage -tile 1x2 -border 0 -mode concatenate -background " + spacingColor +
              " " + strip_print + " " + strip_print + " " + strip_print
              )  # NOTE - wand/pgmagick doesn't support montage, so building use system process calls
    image = Image(filename=strip_print)
    image.border(spacingColor, 90, 90)
    image.save(filename=strip_print)
    return strip_print


def print_it(file_to_print):
    conn = cups.Connection()
    conn.printFile("Selphy", file_to_print, file_to_print, {})


if __name__ == "__main__":
    import getpass

    check_photos()  # sanity check for correct setup
    # check_user(getpass.getuser())  # sanity check for correct user
    check_camera()  # sanity check for camera attached
    check_printer()
    create_folders()  # ensure required folders exist

    # need a loop that just runs forever, and when ready_to_process we do things, then return to the loop
    while True:
        if ready_to_process():
            print('processing!!!')
            destination_directory = get_images()
            print_file = make_print(destination_directory)
            print_it(print_file)
        else:
            print('waiting for photos!!!')
            time.sleep(5)
