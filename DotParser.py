#! /usr/bin/python

#Master-Thesis dot parsing framework
#Date: 14.01.2014
#Author: Bruno-Johannes Schuetze
#uses the djikstra algorithm implemented by David Eppstein
#uses python 2.7.6
#execution: 
#python DotParser.py [path_to_graph] [name_of_output_graph]

#DOT FILE FORMAT
"""
graph Test {
	node [shape=box]
	edge [len=2]
	overlap=false
	1 -- 2[label=3, bandwidth=20, delay = 2, latency=2, throughput=17];
	...
}
"""

import sys
import pydot
import pyparsing
import json
import pickle
import copy
import subprocess
from libraries.dijkstra import *

from utilities import drawGraph_
from utilities import counter_
from utilities import detVPnumb_
from Views import traceroute_
from Views import alto_

#
#Function definitions:
#
#function takes a dictionary and creats a sub_dictionary within, based on supplied values
def insertEdge(outerDict, key1, key2, value):
	innerDict = {}


	if key1 in outerDict:
		innerDict = outerDict[key1]
		innerDict[key2] = value
		outerDict[key1] = innerDict
	else:
		innerDict[key2] = value
		outerDict[key1] = innerDict

#removes dublicates from a list
def removeDublicates(seq):
	keys = {}
	for s in seq:
		keys[s] = 1
	return keys.keys()

#iterates a list to get the keys to sum up values stored in a dict (Alto Map) *********PING*********?????????????????????????????
def getTotalPathCosts(providedMap, pathList):

	total=0
	for x in range(len(pathList)-1):
		key = ((pathList[x])*100000+(pathList[x+1]))
		total = total + providedMap[key]

	return total

#find the smalles value on a path (basically used to find min bandwidth & throughput)
def getMinValue(providedMap, pathList):
	minValue=999999
	for x in range(len(pathList)-1):
		key = ((pathList[x])*100000+(pathList[x+1]))
		tempMin= providedMap[key]
		if tempMin<minValue:
			minValue=tempMin
	return minValue

#generates the sub dictionary to build the "real" cost Map. It takes a len(networkmap) 
#length List with shortest paths from one particular PID to all PID's

def genSubCostDict(constList,someCostMap):
	
	subDict = {}
	edgeCost = 0
	src = 0
	dst = 0
	shortList = constList
	
	
	for x in range(len(shortList)):
			tempList=shortList[x]
			#print "genSub tempList content: ", tempList
			#print "tempList length: ", len(tempList)
			if len(tempList)==1:
				#print "We in here!"
				edgeCost = 0
				dst = tempList.pop(0)
				#subDict[res] = edgeCost
			else:
				src = tempList.pop(0)

				while tempList:
					#if len(tempList) >=1: 
					dst = tempList.pop(0)
					#try:
					#print "SRC: ", src
					#print "DST: ", dst
					edgeCost = edgeCost + int(someCostMap[src*100000+dst])
					src = dst
				#print subDict
			#print "About to insert: ", dst
			#print "With value: ", edgeCost
			subDict[dst]=edgeCost
			edgeCost=0
			
	return subDict


#currently not used, because we are converting all .dot node names to int.
"""def genNetworkList(nodeList):
	resultNetworkMap = []
	for n in nodeList:
		name = n.get_name()
		#if (n is not "node") and (n is not "edge"):
		if not (name == "node" or name == "edge"):
		#if not name == "node" and not name == "edge":
			resultNetworkMap.append(name)
			#print name
	resultNetworkMap.sort()
	return resultNetworkMap
"""
def genBaseNetworkMap(rawNetworkMap): #Method generates the base networkmap i.e. 1 pid = 1 node
	sorted(rawNetworkMap, key = int)
	#print "Sorted: ", rawNetworkMap
	tempDict = {}
	for x in range(1, len(rawNetworkMap)+1):
		tmp = "PID"+str(x)
		tempDict[tmp]=rawNetworkMap.pop(0) #take the first item in the list
	#print tempDict
	return tempDict
	





#function that aggegates nodes based on their link costs. TODO this is the old way of aggregating see makeNetworkMap()
def aggregatePids(edgeMap, threshold, neighborHoodDict):
	noMore = 1
	pidCount = 0
	pidsContent = {}
	networkMap = {}
	tmpNodeList = []
	Round = 0
	pidName = ""
	while (noMore):
		Round+= 1
		#print "ROUND: %d PID: %s" % (Round, pidName)
		nodeList = []
		key = getMin(edgeMap)#get the key for lowes value in dictionary
		dest = key % 100000
		src = key / 100000
		reverseKey = (dest*100000)+src
		if(src == 0 and dest == 0):
			break
		#print "REMOVING: %d and: %d" % (key, reverseKey)
		if (edgeMap[key] < threshold and edgeMap[reverseKey] < threshold ):
			#print "THE EDGEMAP Leftovers: "
			#print edgeMap
			pidCount += 1
			tmpNodeList.append(src)
			tmpNodeList.append(dest)
			pidName = "PID"+str(pidCount)
			#print "Aggregated nodes: ", tmpNodeList
			del edgeMap[key]
			del edgeMap[reverseKey]
			#networkMap[pidName] = tmpNodeList
			updateHood(neighborHoodDict, src, dest)
			updateEdgeList(edgeMap, src, dest)
			updateNetworkMap(src, dest, networkMap)
			#print "\nTHE RESULTS ARE IN<<<<<<<<<<<<<<<<<<<<<<<<<8>>>>>>"
			#print neighborHoodDict
			#print "WE HAVE A NETWORKMAP: "
			#print networkMap
		else:
			noMore=0
	#print "#### FINISHED Neighborhood#### : ", neighborHoodDict
	#print "**** FINISHED NETWORKMAP  **** : ", networkMap
	return networkMap
#updates the neighborhoodDict: removes entries of aggregated devices (node2), names the aggregated nodes the value of node1, 
#and if multiple edges connect the same neighbor it keeps the cheaper
def updateHood(neighborHoodDict, node1, node2):
	tempDict = neighborHoodDict[node1]
	tempDict2 = neighborHoodDict[node2]
	del neighborHoodDict[node1]
	del neighborHoodDict[node2]
	del tempDict[node2]
	del tempDict2[node1]

	#delete entry of node joining with
	#join other entries
	#if both have the same neighbor take lower edge

	loopTempDict = tempDict.copy()
	#Delete the occurence of one another in their own 
	for key in loopTempDict:#TODO DEBUG
		if key in tempDict2:
			if tempDict[key] < tempDict2[key]:
				#print "DELETING: ", key, tempDict2[key]
				del tempDict2[key]
			else:
				#print "DELETING: ", key, tempDict[key]
				del tempDict[key]
	tempDict.update(tempDict2)
	#print "Neighbors: %d : %d contain: " % (node1, node2), tempDict
	for key in tempDict:
		#print "I AM HERE WITH VALUE: ", key
		temp = neighborHoodDict[key]
		del neighborHoodDict[key]
		loopTemp = temp.copy()
		for key2, value2 in loopTemp.items():
			#print "I am here with value: ", key2
			if node2 == key2:
				#print "I WAS HERE deleting:",key2, temp[key2]
				if node1 in loopTemp.keys():
					#print "Node %d in " % node1, loopTemp.keys()
					#print "IS %d with %d < %d with %d ?"%(node1, temp[node1], node2, temp[node2])
					if temp[node1] < temp[node2]:
						#print "now deleting: ", node2 
						del temp[node2]
					else:
						del temp[node2]
						temp[node1] = value2
				else:
					del temp[node2]
					temp[node1] = value2
		neighborHoodDict[key]=temp
	#print "result from update: "
	#print tempDict
	neighborHoodDict[node1]=tempDict


#This method takes a dictionary containing all edges (key format "src*100000+dest") as argument and returns the lowes value 
def getMin(edgeMap):
	tempMin = 999999
	minimum = 999999
	pos = 0
	for key in edgeMap: #x is all the keys in the dictionary
		tempMin = edgeMap[key]
		if tempMin<minimum:
			minimum = tempMin
			pos = key
	return pos



#corrects the entries in the costMap.
#removes entries containing aggregated nodes (node2) and replaces it with the value of node1
def updateEdgeList(edgeList, node1, node2):
	loopList=edgeList
	for key, value in loopList.items():
		eNode1 = key / 100000
		eNode2 = key % 100000
		if eNode1 == node2:
			del edgeList[key]
			tmpEdge =  node1 * 100000 + eNode2
			edgeList[tmpEdge] = value
		if eNode2 == node2:
			del edgeList[key]
			tmpEdge =  eNode1 * 100000 + node1
			edgeList[tmpEdge] = value

#update the networkmap that keeps track what nodes are aggregated into pids
#checks wether aggNode is in networkMap. Stores aggNode under node.
def updateNetworkMap(node, aggNode, networkMap):
	tempList = []
	#print tempList
	if node in networkMap.keys():#if node is already present
		if aggNode in networkMap.keys():#aggNode also already
			networkMap[node].append(aggNode)
			networkMap[node] += networkMap[aggNode]
			del networkMap[aggNode]
		else:#only node is in it
			#print networkMap[node]
			tempList = networkMap[node]
			tempList.append(aggNode)
			networkMap[node] = tempList
	elif aggNode in networkMap.keys():#only aggNode is in it
		networkMap[node] = networkMap[aggNode]
		del networkMap[aggNode]
	else:#none are in it
		tempList.append(aggNode)
		tempList.append(node)
		networkMap[node]=tempList
		#print "UPDATING NETWORKMAP: ", networkMap

#This function takes a nested dictionary and changes the Keynames to PID#
def labelNetworkMap(neighborHood, networkMap):
	pidCount=1
	referenceDict={}
	loopMap = neighborHood.copy()
	tempDict={}
	missingNetMapEntries = []
	#first map PID to router ID
	for key in loopMap.keys():
		pidName = "PID"+str(pidCount)
		referenceDict[key]=pidName
		pidCount+=1
	#second replace router IDs with PIDs in neighborhood
	for key, subDict in loopMap.items():
		del neighborHood[key]
		for key2,value in subDict.items():
			tempDict[referenceDict[key2]] = value
		neighborHood[referenceDict[key]] = tempDict
		tempDict={}
	#third update networkMap (groupings what nodes belong to what PID)
	loopNetworkMap = networkMap.copy()
	for key, value in loopNetworkMap.items():
		del networkMap[key]
		networkMap[referenceDict[key]]=value
	#fourth place the missing entries, the not aggregated Nodes in networkMap
	for key, value in referenceDict.items():
		if value not in networkMap.keys():#add to networkmap
			tempList=[key]
			networkMap[value] = tempList
		#else do noting, cause node already aggregated and in networkMap
	#print "REFERENCE DICT"
	#print referenceDict
	
	
#********************************************************************
########################### PROGRAM START ###########################
#********************************************************************



#variable for hashing
HASH_MULTIPLIER = 100000

#shortest path starting & ending points
path  = str(sys.argv[1])
#start = int(sys.argv[2])
#end   = int(sys.argv[3])
#PIDThreshold = 10#int(sys.argv[4])
graphName = str(sys.argv[2])

#import dot file
graph = pydot.graph_from_dot_file(path) 
#grabbing the list of edges
edgeList = graph.get_edge_list()
#storing the list of nodes

nodeList =  graph.get_node_list()

print "generating ground truth"
#draw the complete network or ground truth
subprocess.Popen(["neato", "-Tjpeg", path, "-o","Output/"+graphName+"_GTRUTH"])

#Holds the nodes with its neighbors and associated edge weights
dijkstraFormatDict = {} # used for dijkstra and aggregation 

#List of all ID's used (PIDS)
#rawNetworkMap = genNetworkList(nodeList)
#print rawNetworkMap
fakenodesList = []
pathCostMap = {}	#Map with hasehd node names as key and cost as value
#attributes = []	#List of all attributes

latencyMap 	= {} #
#bandwidthMap 	= {} #
#throughputMap 	= {} 
#delayMap   	= {}
interfaceMap	= {}
aliasResMap	= {}#contains true falls wether edges can resolve to nodes
altoPID_Map	= dict() #contains the 

#BUILDING NETWORK AND COST MAP!!!!-----------------------------------------

#parsing and splitting up into all the different maps

print "generating ALTO meta."
for e in edgeList:
	#tempDict.clear()	
	src   = int(e.get_source()) 
	dest  = int(e.get_destination())
	label = int(e.get_label())#label = weights of a edge
	
	#print "TEST: ", src*100000+dest
	#if (label != 0):
	interfaceMap[(src*100000) + dest] = e.get_headlabel()
	tempAttr = json.dumps(e.get_attributes())
	edgeAttr = json.loads(tempAttr)
		
	insertEdge(dijkstraFormatDict, src, dest, label)
	insertEdge(dijkstraFormatDict, dest, src, label)
	
	fakenodesList.append(src)	#add nodes to networkmap
	fakenodesList.append(dest)	#add nodes to networkmap
	pathCostMap[(src*100000) + dest] = label
		#pathCostMap[(dest*100000) + src] = label
		#delayMap[(src*100000) + dest] = int(edgeAttr['delay'])
		#throughputMap[(src*100000) + dest] = int(edgeAttr['throughput'])
	latencyMap[(src*100000) + dest] = float(edgeAttr['latency'])
		#bandwidthMap[(src*100000) + dest] = int(edgeAttr['bandwidth'])
	aliasResMap[(src*100000) + dest] = int(edgeAttr['alias'])

#generating a mapping: "node name" to PID
test_stuff = dict()

for n in nodeList:
	if n.get_name() is 'node':
			continue
	if n.get_name() is 'edge':
			continue
	name   = int(n.get_name())
	#print "NODE LIST: ", name
	#altoPID_Map[name] = str(n.get_label())
	
	tempAttr = json.dumps(n.get_attributes())
	nodeAttr = json.loads(tempAttr)
	if (str(nodeAttr['comment']) != 'PID0'):
		altoPID_Map[name] =  str(nodeAttr['comment'])
	#if str(nodeAttr['comment'])!= 'PID0':
	#	nodeList.append(n)
	#print altoPID_Map

print "done"
#print altoPID_Map	
#shortest path algorithm based on Dijkstra
#dijk,Predecessors = Dijkstra(dijkstraFormatDict, start, end)
#shortPathList = shortestPath(dijkstraFormatDict, start, end)
fakenodesList = removeDublicates(fakenodesList)
fakenodesList = sorted(fakenodesList)


#building a "real" Alto cost map. From all PIDs to all PID

tempList = []
#List that contains all shortest paths from all nodes to all nodes
totalSPathDict = {}
innerSPathDict = {}
rawCostMap = {}	#lists costs from all to nodes, to all nodes
tempDict = {}

print "running djikstra."

#for x in range(1,len(fakenodesList)+1):
for x in fakenodesList:
	#print "Outter: ", x
	#for y in range(1,len(fakenodesList)+1):
	for y in fakenodesList:
		shortPathList = shortestPath(dijkstraFormatDict, x, y)
		tempList.append(shortPathList)
		#assign the shortestpath from x to y to a dict with key y
		innerSPathDict[y] = shortPathList
	# 2 Level Dictionary.Key x (src) contains a dictionary with key y (dest) who's value is the list of nodes on the shortest path between src & dest
	totalSPathDict[x] = copy.deepcopy(innerSPathDict)#deepcopying objects containing objects
	#print "total shortest path dictionary"
	#print totalSPathDict
	rawCostMap[x]=genSubCostDict(tempList, pathCostMap)
	tempList = [] #clearing tempList
	#innerSPathDict = {}
print "done"

#This function basically looks how many links can be found with the in the network defined vantage points
#TODO### enable ###TODO#  to generate statistical data. 
#un_used = detVPnumb_.genVpStatistics(nodeList, totalSPathDict, graphName)

print "generating ALTO maps:"

print "\t* Network map"
#aggNetMap = aggregatePids(pathCostMap, PIDThreshold, dijkstraFormatDict)
altoNetworkMap = alto_.makeNetworkMap(altoPID_Map)
print "\t* Cost map"
altoCostMap = alto_.genAltoCostMap(altoPID_Map, dijkstraFormatDict)

print "generating ALTO jpgs."
#DRAW A VISIAL REPRESENTATION OF THE AGGREGATED NETWORK *******ALTO VIEW********
drawGraph_.drawGraph(altoCostMap, graphName+'_ALTO')

#network map
realNetworkMap = open("Output/ALTO/"+graphName+"_ALTO_NETWORK_MAP.txt", 'w+')
realNetworkMap.write(str(altoNetworkMap))
realNetworkMap.close()
nwmFh = open("Objects/ALTO_NWM_pickle.obj", "w+")
pickle.dump(altoNetworkMap, nwmFh)
nwmFh.close()


fd = open("Objects/node_to_pid_pickle.obj", "w+")
pickle.dump(altoPID_Map, fd)
fd.close()

#cost map 
realCostMap = open("Output/ALTO/"+graphName+"_ALTO_COST_MAP.txt", 'w+')
realCostMap.write(str(altoCostMap))
realCostMap.close()

fd = open("Objects/ALTO_pickle.obj", "w+")
pickle.dump(altoCostMap, fd)
fd.close()

print "running traceroutes"
#GENERATE AND DRAW A VISIAL REPRESENTATION OF THE TRACED NETWORK *******TRACEROUTE VIEW********
tracerouteDict = traceroute_.genTracerouteView(aliasResMap, latencyMap, nodeList, totalSPathDict, interfaceMap, graphName)

tracrouteFile = open("Output/TRACEROUTE/"+graphName+"_TRACEROUTE_VIEW.txt", 'w+')
tracrouteFile.write(str(tracerouteDict))
tracrouteFile.close()

tf = open("Objects/TR_pickle.obj", "w+")
pickle.dump(tracerouteDict,tf)
tf.close()



print "generating traceroute jpgs.\n"
drawGraph_.drawTracerouteView(tracerouteDict, graphName+'_TR')
drawGraph_.drawNetworkMap(altoNetworkMap, graphName+'_NETWORKMAP')
#generate outputfile with statistics of edge and node count (outdated and not accurate anymore)
#counter_.genStats()

print "starting mergeTool.py"
subprocess.call(["./utilities/mergeTool.py", graphName])


print "\nDONE, please see the Output folder for the 3 resulting Views:"
print "\n\t"+graphName+"_GTRUTH\t(ground truth)"
print "\t"+graphName+"_ALTO \t(Alto)"
print "\t"+graphName+"_TR \t(traceroute)\n"
print "\n\tNode & Edge count: TOTAL_STATS_COUNT.txt\n"
print "\tAlto Maps:"
print "\tALTO/"+graphName+"_ALTO_NETWORK_MAP.txt"
print "\tALTO/"+graphName+"_ALTO_COST_MAP.txt\n"
print "\tTraceroute path latencies:"
print "\tTRACEROUTE/"+graphName+"_LATENCY.txt\n"
print "\tMergeTool Results:\n\t Output/RESULTS/"+graphName+"_MergeResult.txt\n"
print "\tIf output of VP stats is enabled:"
print "\tOutput/VANTAGEPOINTS/"+graphName+"vpStats.txt\n" 


