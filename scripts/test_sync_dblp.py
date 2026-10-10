import copy
import unittest
import sync_dblp as sync


def rows(names=None, book='ICML', title='Efficient learning', url='https://dblp.org/rec/conf/icml/Test26'):
    names = names or ['Alice', sync.AUTHOR_NAME]
    output = []
    for i, name in enumerate(names, 1):
        values = dict(paper=url, title=title, year='2026', sig=f'{url}#{i}', ordinal=str(i),
                      authorName=name, creator=sync.DBLP_AUTHOR if name in [sync.AUTHOR_NAME, 'Joey Zhou', 'Tianyi Zhou 0007'] else f'author/{i}',
                      creatorCount=str(len(names)), book=book, venue='International Conference on Machine Learning')
        output.append({k: {'value': v} for k, v in values.items()})
    return output


PAGE = '<p class="result-count">1 publications</p><div class="paper-list"><article class="paper" data-category="0"><h3>Efficient learning</h3></article></div><p id="empty">Empty</p>'
VENUES = {'ccf_a': ['ICML', 'ACL', 'ECCV']}


class EligibilityTests(unittest.TestCase):
    def test_exact_signature_only(self):
        for name in ['Tianyi Zhou', 'Tianyi Zhou 0007', 'Joey Zhou', 'joey tianyi zhou']:
            with self.subTest(name=name):
                self.assertIn('identity:', sync.author_reason(sync.group_records(rows(['Alice', name]))[0]))

    def test_complete_sqlagent_author_order(self):
        r = sync.group_records(rows(['Wenjia Jiang', 'Yiwei Wang 0001', 'Boyan Han', sync.AUTHOR_NAME, 'Chi Zhang 0007']))[0]
        self.assertEqual(r['authors'][-1], 'Chi Zhang 0007')
        self.assertIn('author_order:', sync.author_reason(r))

    def test_numeric_author_ordinals(self):
        r = sync.group_records(list(reversed(rows([f'A{i}' for i in range(11)] + [sync.AUTHOR_NAME]))))[0]
        self.assertIsNone(sync.author_reason(r))

    def test_wrong_profile_is_rejected(self):
        data = rows(); data[-1]['creator']['value'] = 'someone-else'
        self.assertIn('identity:', sync.author_reason(sync.group_records(data)[0]))

    def test_incomplete_sources_fail_closed(self):
        for data in [[], rows()[:-1], rows()[1:]]:
            with self.assertRaises(ValueError): sync.group_records(data)
        for key in ['authorName', 'ordinal', 'creatorCount']:
            data = rows()
            for row in data: row.pop(key)
            with self.assertRaises(ValueError): sync.group_records(data)

    def test_duplicate_signature_join_rows_are_safe(self):
        data = rows(); self.assertEqual(len(sync.group_records(data + data)[0]['authors']), 2)

    def test_child_venues_do_not_inherit_rank(self):
        for book in ['ACL (Findings)', 'ACL (Student Research Workshop)', 'Workshop@ACL', 'ACL (Short Papers)']:
            r = sync.group_records(rows(book=book))[0]
            self.assertIsNone(sync.eligible_venue(r, sync.top_tier_venue_keys(VENUES)))
        r = sync.group_records(rows(book='ECCV (20)'))[0]
        self.assertEqual(sync.eligible_venue(r, sync.top_tier_venue_keys(VENUES)), 'ECCV')

    def test_existing_manual_entry_has_no_exemption(self):
        for data in [rows([sync.AUTHOR_NAME, 'Alice']), rows(book='WACV')]:
            updated, pending, audit = sync.rebuild(PAGE, data, {}, VENUES)
            self.assertEqual(audit['published_count'], 0)
            self.assertNotIn('<article', updated)
            self.assertEqual(len(audit['removed']), 1)

    def test_uncertain_new_category_waits_for_user(self):
        data = rows(title='Unclassified title')
        _, pending, audit = sync.rebuild(PAGE, data, {}, VENUES)
        self.assertEqual(len(pending), 1)
        self.assertEqual(audit['published_count'], 0)
        _, pending, audit = sync.rebuild(PAGE, data, {'unclassified title': 'Trustworthy AI'}, VENUES)
        self.assertEqual(len(pending), 0)
        self.assertEqual(audit['published'][0]['category'], 1)

    def test_rebuild_is_idempotent_and_preserves_surrounding_page(self):
        updated, _, _ = sync.rebuild(PAGE, rows(), {}, VENUES)
        again, _, audit = sync.rebuild(updated, rows(), {}, VENUES)
        self.assertEqual(updated, again)
        self.assertEqual(audit['removed'], [])
        self.assertTrue(updated.endswith('<p id="empty">Empty</p>'))

    def test_verified_supplements_obey_same_filters(self):
        item = dict(title='Efficient supplement', year='2026', url='https://example.org/paper',
                    authors=['Alice', sync.AUTHOR_NAME], venue='ICML', sources=['https://example.org/evidence'], verified_on='2026-10-10')
        for names, venue, expected in [(['Alice', sync.AUTHOR_NAME], 'ICML', 2),
                                      ([sync.AUTHOR_NAME, 'Alice'], 'ICML', 1),
                                      (['Alice', 'Joey Zhou'], 'ICML', 1),
                                      (['Alice', sync.AUTHOR_NAME], 'WACV', 1)]:
            _, _, audit = sync.rebuild(PAGE, rows(), {}, VENUES, [{**item, 'authors': names, 'venue': venue}])
            self.assertEqual(audit['published_count'], expected)
        with self.assertRaises(ValueError): sync.verified_records([{**item, 'sources': []}], [])
        self.assertEqual(sync.verified_records([{**item, 'title': 'Efficient learning'}], sync.group_records(rows())), [])

    def test_unicode_title_dedup(self):
        self.assertEqual(sync.key_title('Efﬁcient AI.'), sync.key_title('Efficient AI'))


if __name__ == '__main__':
    unittest.main()
