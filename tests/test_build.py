import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/animate-architecture'
sys.path.insert(0,str(SKILL/'scripts'))
from build import build
from validate_diagram import validate


class DiagramBuildTests(unittest.TestCase):
    def setUp(self):
        self.order=json.loads((SKILL/'assets/order-flow.json').read_text())

    def test_two_distinct_topologies_build_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            results=[]
            for name in ('agent-tree','order-flow'):
                target=Path(tmp)/(name+'.html')
                results.append(build(SKILL/'assets'/f'{name}.json',target))
                self.assertTrue(target.is_file() and target.stat().st_size>10000)
            self.assertEqual([r['nodes'] for r in results],[7,5])
            self.assertEqual([r['steps'] for r in results],[12,6])

    def test_reject_detached_endpoint(self):
        data=copy.deepcopy(self.order);data['routes'][0]['points'][0][0]+=2
        with self.assertRaises(ValueError):validate(data)

    def test_reject_route_through_a_node(self):
        data=copy.deepcopy(self.order)
        data['routes'].append({'id':'bad','source':'client','target':'warehouse','points':[[290,275],[970,275],[970,470]]})
        with self.assertRaises(ValueError):validate(data)

    def test_reject_crossed_feedback_channel(self):
        data=copy.deepcopy(self.order)
        data['routes'].append({'id':'bad','source':'client','target':'orders','points':[[170,360],[170,420],[340,420],[340,280],[400,280]]})
        with self.assertRaises(ValueError):validate(data)

    def test_reject_unknown_state_and_flow_references(self):
        for key,value in [('activeRoutes',['missing']),('nodeStates',{'missing':{'state':'READY'}})]:
            data=copy.deepcopy(self.order);data['steps'][0][key]=value
            with self.assertRaises(ValueError):validate(data)

    def test_reject_nonfinite_and_zero_duration(self):
        for value in (float('nan'),float('inf'),0,-1):
            data=copy.deepcopy(self.order);data['steps'][0]['duration']=value
            with self.assertRaises(ValueError):validate(data)

    def test_embedded_text_does_not_end_the_data_script(self):
        data=copy.deepcopy(self.order);data['title']='literal </script><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'diagram.json';source.write_text(json.dumps(data));target=Path(tmp)/'index.html';build(source,target)
            from html.parser import HTMLParser
            class ScriptReader(HTMLParser):
                inside=False;payload=''
                def handle_starttag(self,tag,attrs):
                    self.inside=tag=='script' and dict(attrs).get('id')=='diagram-data'
                def handle_endtag(self,tag):
                    if tag=='script':self.inside=False
                def handle_data(self,value):
                    if self.inside:self.payload+=value
            reader=ScriptReader();reader.feed(target.read_text())
            self.assertEqual(json.loads(reader.payload)['title'],data['title'])


if __name__=='__main__':unittest.main()
