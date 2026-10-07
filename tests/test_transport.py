"""Focused checks for the public local research transport."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('cockpit_app',Path(__file__).parents[1]/'app.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TransportChecks(unittest.TestCase):
    def setUp(self):
        module.tablet_data_store.clear()
        self.controller=module.socketio.test_client(module.app)
        self.tablet=module.socketio.test_client(module.app)
    def tearDown(self):
        self.controller.disconnect()
        self.tablet.disconnect()
    def test_settings_broadcast_once_and_clear_previous_task(self):
        module.tablet_data_store.append({'subjectId':'DEMO-OLD'})
        command={'action':'syncSettings','id':'DEMO-001','group':'L_ABC-H_BCA'}
        self.controller.emit('command',command)
        received=[x for x in self.tablet.get_received() if x['name']=='cmd_from_server']
        self.assertEqual(len(received),1)
        self.assertEqual(received[0]['args'][0],command)
        self.assertEqual(module.tablet_data_store,[])
    def test_task_event_visible_and_exported(self):
        event={'type':'click','result':'correct','subjectId':'DEMO-001','score':1,'rt':350,'timestamp':'synthetic'}
        self.tablet.emit('tablet_event',event)
        received=self.controller.get_received()
        self.assertTrue(any(x['name']=='status_from_tablet' and x['args'][0]['event']=='Tablet_Correct' for x in received))
        self.controller.emit('request_tablet_data')
        download=next(x for x in self.controller.get_received() if x['name']=='data_ready_download')
        self.assertIn('DEMO-001,click,correct,1,350',download['args'][0]['content'])

if __name__=='__main__':
    unittest.main()
