import shutil
import unittest

import cups
import mock

from main import *


def clean_up():
    if os.path.exists(imageStore):
        shutil.rmtree(imageStore)


class MainTest(unittest.TestCase):

    def setUp(self):
        clean_up()

    def tearDown(self):
        clean_up()

    def test_valid_default_alignment(self):
        f = open('logo.jpg', 'w')
        f.close()
        check_photos()
        self.assertTrue(True)
        os.remove('logo.jpg')

    def test_valid_alignment(self):
        f = open('somePhoto.JPG', 'w')
        f.close()
        check_photos(3, 3, 8, 'somePhoto.JPG')
        self.assertTrue(True)
        os.remove('somePhoto.JPG')

    def test_valid_alignment_bad_logo(self):
        self.assertRaises(ValueError, check_photos, 3, 3, 8, 'somePhoto.JPG')

    def test_valid_alignment_no_logo(self):
        check_photos(3, 3, 9, None)
        self.assertTrue(True)

    def test_invalid_alignment(self):
        self.assertRaises(ValueError, check_photos, 3, 3, 9, 'somePhoto.JPG')

    def test_valid_user(self):
        check_user('root')
        self.assertTrue(True)

    def test_invalid_user(self):
        self.assertRaises(UserWarning, check_user, 'max')

    def test_folders_do_not_exist(self):
        create_folders()
        self.assertTrue(os.access(imageStore, os.X_OK | os.W_OK))

    def test_folders_do_exist(self):
        create_folders()
        create_folders()
        self.assertTrue(os.access(imageStore, os.X_OK | os.W_OK))

    @mock.patch('main.gp')
    def test_no_camera_connected(self, mock_gp):
        mock_gp.gp_camera_init.return_value = -1
        mock_gp.GP_OK = 0
        self.assertRaises(UserWarning, check_camera)

    @mock.patch('main.gp')
    def test_camera_connected(self, mock_gp):
        mock_gp.gp_camera_init.return_value = 0
        mock_gp.GP_OK = 0
        check_camera()
        self.assertTrue(True)

    @mock.patch.object(cups, 'Connection')
    def test_no_printer_connected(self, mock_cups):
        mock_cups.getPrinters.return_value = []
        self.assertRaises(UserWarning, check_printer)

    @mock.patch.object(cups, 'Connection')
    def test_bad_printer_connected(self, mock_cups):
        mock_cups.getPrinters.return_value = ['123']
        self.assertRaises(UserWarning, check_printer)

    # # @mock.patch.object(cups, 'Connection')
    # def test_printer_connected(self):
    #     with mock.patch(cups.Connection.getPrinters, mock.MagicMock(return_value=[123])):
    #         check_printer()
    #         self.assertTrue(True)

    @mock.patch('main.gp')
    @mock.patch('main.list_files')
    def test_not_enough_to_go_none(self, mock_list, mock_gp):
        mock_list.return_value = []
        self.assertFalse(ready_to_process())

    @mock.patch('main.gp')
    @mock.patch('main.list_files')
    def test_not_enough_to_go_two(self, mock_list, mock_gp):
        mock_list.return_value = ['photo1.JPG', 'photo1.NEF', 'photo2.JPG', 'photo2.NEF']
        self.assertFalse(ready_to_process())

    @mock.patch('main.gp')
    @mock.patch('main.list_files')
    def test_enough_to_go_three(self, mock_list, mock_gp):
        mock_list.return_value = ['photo1.JPG', 'photo1.NEF', 'photo2.JPG', 'photo2.NEF', 'photo3.JPG', 'photo3.NEF']
        self.assertTrue(ready_to_process())


if __name__ == '__main__':
    unittest.main()
