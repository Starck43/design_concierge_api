import unittest

from bot.handlers.common import check_user_in_groups


class TestCheckUserInGroups(unittest.TestCase):

    def test_check_user_in_groups(self):
        # Test case 1: User belongs to the allowed group
        groups = [1]
        allowed_codes = ["O"]
        result = check_user_in_groups(groups, allowed_codes)
        self.assertTrue(result)

        # Test case 2: User belongs to multiple allowed groups
        groups = [0, 1]
        allowed_codes = ["D", "DO", "S"]
        result = check_user_in_groups(groups, allowed_codes)
        self.assertTrue(result)

        # Test case 3: User does not belong to the allowed group
        groups = [0]
        allowed_codes = ["O", "S"]
        result = check_user_in_groups(groups, allowed_codes)
        self.assertFalse(result)

        # Test case 4: User does not belong to any group
        groups = []
        allowed_codes = ["D", "DO", "S"]
        result = check_user_in_groups(groups, allowed_codes)
        self.assertFalse(result)

        # Test case 5: User group is uncategorized
        groups = [3]
        allowed_codes = ["D", "O"]
        result = check_user_in_groups(groups, allowed_codes)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
