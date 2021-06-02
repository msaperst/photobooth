import unittest

from main import *


def clean_up():
    if os.path.exists(imageQueue):
        shutil.rmtree(imageQueue)
    if os.path.exists(imageStore):
        shutil.rmtree(imageStore)
    if os.path.exists(imageBackup):
        shutil.rmtree(imageBackup)


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
        f = open('somePhoto.jpg', 'w')
        f.close()
        check_photos(3, 3, 8, 'somePhoto.jpg')
        self.assertTrue(True)
        os.remove('somePhoto.jpg')

    def test_valid_alignment_bad_logo(self):
        self.assertRaises(ValueError, check_photos, 3, 3, 8, 'somePhoto.jpg')

    def test_valid_alignment_no_logo(self):
        check_photos(3, 3, 9, None)
        self.assertTrue(True)

    def test_invalid_alignment(self):
        self.assertRaises(ValueError, check_photos, 3, 3, 9, 'somePhoto.jpg')

    def test_valid_user(self):
        check_user('root')
        self.assertTrue(True)

    def test_invalid_user(self):
        self.assertRaises(UserWarning, check_user, 'max')

    def test_folders_do_not_exist(self):
        create_folders()
        self.assertTrue(os.access(imageQueue, os.X_OK | os.W_OK))
        self.assertTrue(os.access(imageStore, os.X_OK | os.W_OK))
        self.assertTrue(os.access(imageBackup, os.X_OK | os.W_OK))
        self.assertTrue(os.access(os.path.join(imageStore, 'prints'), os.X_OK | os.W_OK))

    def test_folders_do_exist(self):
        create_folders()
        create_folders()
        self.assertTrue(os.access(imageQueue, os.X_OK | os.W_OK))
        self.assertTrue(os.access(imageStore, os.X_OK | os.W_OK))
        self.assertTrue(os.access(imageBackup, os.X_OK | os.W_OK))
        self.assertTrue(os.access(os.path.join(imageStore, 'prints'), os.X_OK | os.W_OK))

    def test_not_enough_to_go_none(self):
        create_folders()
        self.assertFalse(ready_to_process())

    def test_not_enough_to_go_two(self):
        create_folders()
        f = open(os.path.join(imageQueue, 'photo1.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo2.jpg'), 'w')
        f.close()
        self.assertFalse(ready_to_process())
        os.remove(os.path.join(imageQueue, 'photo1.jpg'))
        os.remove(os.path.join(imageQueue, 'photo2.jpg'))

    def test_not_enough_to_go_three(self):
        create_folders()
        f = open(os.path.join(imageQueue, 'photo1.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo2.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo3.jpg'), 'w')
        f.close()
        self.assertTrue(ready_to_process())
        os.remove(os.path.join(imageQueue, 'photo1.jpg'))
        os.remove(os.path.join(imageQueue, 'photo2.jpg'))
        os.remove(os.path.join(imageQueue, 'photo3.jpg'))

    def test_not_enough_to_go_five(self):
        create_folders()
        f = open(os.path.join(imageQueue, 'photo1.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo2.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo3.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo4.jpg'), 'w')
        f.close()
        f = open(os.path.join(imageQueue, 'photo5.jpg'), 'w')
        f.close()
        self.assertTrue(ready_to_process())
        os.remove(os.path.join(imageQueue, 'photo1.jpg'))
        os.remove(os.path.join(imageQueue, 'photo2.jpg'))
        os.remove(os.path.join(imageQueue, 'photo3.jpg'))
        os.remove(os.path.join(imageQueue, 'photo4.jpg'))
        os.remove(os.path.join(imageQueue, 'photo5.jpg'))


if __name__ == '__main__':
    unittest.main()
