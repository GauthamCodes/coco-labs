import json,sys
from coco_lab.compare_loop import LoopComparison
from coco_lab.control import MPPI
trace=[]
dwa_cycles=[]
from coco_lab.control import LocalWindow
windows=[]
frames=[]
window_init=LocalWindow.__init__
def init(self,belief,ranges,angles,mount,path,params):
 window_init(self,belief,ranges,angles,mount,path,params)
 windows.append({'belief':belief,'ranges':list(ranges),'angles':list(angles),'mount':mount,'ox':self.ox,'oy':self.oy,'n':self.n,'res':params.resolution,'grid':list(self.cost_grid),'ray_indices':[self.index(belief[0]+__import__('math').cos(belief[2])*mount[0]-__import__('math').sin(belief[2])*mount[1]+r*__import__('math').cos(belief[2]+mount[2]+a),belief[1]+__import__('math').sin(belief[2])*mount[0]+__import__('math').cos(belief[2])*mount[1]+r*__import__('math').sin(belief[2]+mount[2]+a)) if r<=params.mark_range else None for a,r in zip(angles,ranges)]})
LocalWindow.__init__=init
from coco_lab.control import DWA
original_compute=DWA.compute
def dwa_compute(self,*args,**kwargs):
 cycle=original_compute(self,*args,**kwargs)
 dwa_cycles.append({'tick':len(frames),'chosen':cycle.chosen,'candidates':[vars(c) for c in cycle.candidates]})
 return cycle
DWA.compute=dwa_compute
original=MPPI._scores
current=[]
def scores(self,poses,window,local,goal,goal_yaw,goal_dist):
 r=original(self,poses,window,local,goal,goal_yaw,goal_dist)
 current.append({'scores':r,'poses':poses,'goal_dist':goal_dist,'local':local,'window':{'ox':window.ox,'oy':window.oy,'resolution':window.params.resolution},'costs':[window.cost(q[0],q[1]) for q in poses[::2]]})
 return r
MPPI._scores=scores
c=LoopComparison(json.loads(world_json),json.loads(request_json))
for t in range(60):
 current=[]
 frames.append(c.advance())
 trace.append(current)
result=json.dumps({'scores':trace,'windows':windows,'frames':frames,'dwa_cycles':dwa_cycles})
