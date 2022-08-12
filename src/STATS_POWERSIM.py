import spssaux, extension
from extension import Template, Syntax, processcmd
import spss
import os
import sys
import time
import tempfile
import platform
import ntpath
#import random
#import string

print_debug = 0

parameter_statement=''
command=''
vary=''
values=''
sz_table = ''
my_syntax = ''
outfile = ''
xname=''
xlabel=''
yname=''
ylabel=''
color_name=''
color_label=''
size_name = ''
size_label = ''
gtype=''
graph_type=''
printback = ''
dsn_closed = True
SLASH = os.path.sep
PLATFORM = platform.system().lower()

def path_leaf(path):
    head, tail = ntpath.split(path)
    return head, tail
    #return tail or ntpath.basename(head)

def GetArgValue (inval):
  outval=''
  if inval[1] == "'":
    outval = inval[2:].strip()
  else:
    outval = inval.strip()
  return outval

def AssignToken(c):
  e = c.find("=")
  l = len(c)
  c = c[e+1:l]
  return c

def AssignVarName (k,Names,Chart,Sz,Labels,strName):
  j = 0
  for i in Names:
    lhs = i.lower()
    rhs = k.lower()
    if lhs == rhs:
      Chart[j]=strName
      Sz[j]=Chart[j]
      if Labels[j].strip() != '':
        Labels[j]=Labels[j] + "(" + k + ")"
      else:
        Labels[j] = k
    j = j + 1
  return Chart,Sz,Labels

def CloseData (dsn):
  global dsn_closed
  import SpssClient
  SpssClient.StartClient()
  DataDocsList = SpssClient.GetDataDocuments()
  for index in range(DataDocsList.Size()):
    ThisDataDoc = DataDocsList.GetItemAt(index)
    DocName = ThisDataDoc.GetDatasetName()
    if DocName.lower() == dsn.lower():
      dsn_closed = False
      if ThisDataDoc.IsActiveDataDoc(): ActiveDataset = DocName
  SpssClient.StopClient()
  return dsn_closed

def CreateGroupingVariable (COMMANDS, KeyVar, NewVar, value_list):
  var_width=9
  for a in value_list:
    if len(a) > var_width: var_width=len(a)

  COMMANDS.append('STRING GVAR (' + "A" + str(var_width).strip() + ').\nSORT CASES BY ' + KeyVar + '.')
  l = len(value_list)
  # Need this pattern:
  #  compute x=1.
  #  if lag(x)=1 x=2.
  #  if lag(x)=2 x=3.

  x = NewVar

  COMMANDS.append("compute " + x + "=1.")
  for a in range(1,l):
    COMMANDS.append("if lag(" + x + ")=" + str(a) + " " + x + "=" + str(a+1) + ".")

  n=0
  COMMANDS.append("EXECUTE.")
  for a in value_list:
    n=n+1
    COMMANDS.append("if " + x + "=" + str(n) + " GVAR='" + a.strip() + "'.")

  COMMANDS.append('SORT CASES BY GVAR.')
  return

def ErrorChecking(spss,DoingThis):
  errorLevel=str(spss.GetLastErrorLevel())
  errorMsg=spss.GetLastErrorMessage()
  if FindString(errorMsg, "No error"): errorMsg="No message is associated with this error number."
  WarningsText="Error number " + errorLevel + ": Text=" + errorMsg + "\nAt least one command did not run."
  print(WarningsText)
  print(DoingThis)
  WarningsTable(WarningsText)
  return errorLevel

def FindString(l, value):
  if isinstance(value, (str)):
    if l.find(str(value)) > -1:
      return True
    else:
      return False

def GetMeasLevel(spss,x,y):
  xCat = False
  yCat = False
  varcount = spss.GetVariableCount()
  for i in range(varcount):
    varname = spss.GetVariableName(i)
    meas_level = spss.GetVariableMeasurementLevel(i)
    if varname.upper() == x.upper():
      if meas_level.upper() != "SCALE": xCat = True
    if varname.upper() == y.upper():
      if meas_level.upper() != "SCALE": yCat = True

  return xCat,yCat

def GetParameters(cmd):
  if cmd == "POWER MEANS ONESAMPLE":
    xlist=['TEST','SIGNIFICANCE','N','POWER','SD','MEAN','NULL','ES']
  elif cmd == "POWER MEANS RELATED":
    xlist=['TEST','SIGNIFICANCE','N','POWER','NRATIO','SD','MEAN','ES']
  elif cmd == "POWER MEANS INDEPENDENT":
    xlist=['TEST','SIGNIFICANCE','N','POWER','NRATIO','SD','MEAN','ES']
  elif cmd == "POWER ONEWAY ANOVA":
    xlist=['SIGNIFICANCE','GROUP_SIZES','POWER','GROUP_WEIGHTS','POOLED_SD','GROUP_MEANS','ES']
  elif cmd == "POWER PROPORTIONS ONESAMPLE":
    xlist=['TEST','ESTIMATE','CONTINUITY','SIGNIFICANCE','N','POWER','NULL','ALTERNATIVE','TIMER']
  elif cmd == "POWER PROPORTIONS RELATED":
    xlist=['TEST','ESTIMATE','SIGNIFICANCE','NPAIRS','POWER','VALUES','MARGINAL','CORRELATION','TIMER']
  elif cmd == "POWER PROPORTIONS INDEPENDENT":
    xlist=['TEST','METHOD','ESTIMATE','CONTINUITY','SIGNIFICANCE','N','POWER','NRATIO','PROPORTIONS','POOLED','TIMER']
  elif cmd == "POWER PEARSON ONESAMPLE":
    xlist=['TEST','ADJUST_BIAS','SIGNIFICANCE','N','POWER','NULL','ALTERNATIVE']
  elif cmd == "POWER SPEARMAN ONESAMPLE":
    xlist=['TEST','VARIANCE','SIGNIFICANCE','N','POWER','NULL','ALTERNATIVE']
  elif cmd == "POWER PARTIALCORR":
    xlist=['TEST','PARTIALOUT','SIGNIFICANCE','N','POWER','NULL','ALTERNATIVE']
  elif cmd == "POWER UNIVARIATE LINEAR":
    xlist=['MODEL','SIGNIFICANCE','N','POWER','TOTAL_PREDICTORS','TEST_PREDICTORS','PARTIAL_CORR','FULL_MODEL','NESTED_MODEL','ES','INTERCEPT']

  return xlist

def GetValue (mystr,s1,s2):
  b1=mystr.find(s1)
  b2=mystr.find(s2)
  n=mystr[0:b1]
  l=mystr[b1+1:b2]
  return n,l

def KeepSyntax(syntax,keep):

# "POWER MEANS ONESAMPLE
#  /PLOT N /PARAMETERS TEST=NONDIRECTIONAL SIGNIFICANCE=0.05 POWER= .8 TO .9 BY .05
#           SD=2 MEAN=1 NULL=0
#  /PRECISION HALFWIDTH=1 2."
#
# Keep only command name and /PARAMETERS statement

  syntax = syntax.replace(' =','=').replace('= ','=')
  first_slash=syntax.find('/')
  command_name=syntax[0:first_slash-1]
  subs=syntax.split('/')
  needed_syntax=''

  for i in subs:
    target_space = i.strip()
    first_word=target_space[0:target_space.find(' ')]
    if FindString(first_word,keep.upper()):
      needed_syntax=command_name + " /" + i
      if needed_syntax[-1] == ".": needed_syntax = needed_syntax[0:len(needed_syntax)-1]
      break
  return needed_syntax

def Make_GGRAPH (graph_type, Test_Type, xname, yname, color_name, size_name, ChartXName, ChartYName, ChartColorName, \
        ChartSizeName, xlabel, ylabel, color_label, size_label, chart_title, chart_subtitle, chart_footnote):

  if (xname.lower() == "power"): gridlines=" /GRIDLINES XAXIS=YES YAXIS=NO"

  if graph_type == "LINE":
    varspec = ChartXName + ' MEAN(' + ChartYName + ')[name="'
    ChartYName = "MEAN_" + ChartYName  #Now change the Y name for the rest of the GPL
    varspec = varspec +ChartYName + '" LEVEL=SCALE] ' + ChartColorName.strip()
  else:
    varspec = ChartXName + ' ' + ChartYName + ' ' + \
      ChartColorName.strip() + ' ' + ChartSizeName.strip()

  if print_debug: print("VARNAMES FOR GRAPHS: " + varspec)

  inlinetemplate = 'INLINETEMPLATE="' + "<setStyle type='scatter'><style size='20pt'/></setStyle>" + '"\n'

  begin = 'BEGIN GPL\n'
  end = 'END GPL.\n'
  gr_begin = 'GGRAPH\n /GRAPHDATASET NAME="graphdataset" VARIABLES=' + varspec
  gr_missing = ' MISSING=LISTWISE\nREPORTMISSING=NO\n /GRAPHSPEC SOURCE=INLINE\n'
  gr_fitline = ' /FITLINE TOTAL=NO SUBGROUP=NO.\n'
  gr_w_inline = gr_begin + gr_missing + inlinetemplate + gr_fitline

  if Test_Type != "TEST":
    if graph_type == "BUBBLE":
      ggraph = gr_w_inline
    else:
      ggraph = gr_begin + gr_missing.replace('SOURCE=INLINE','SOURCE=INLINE.')
  else:
    if graph_type == "BUBBLE":
      ggraph = gr_w_inline
    else:
      ggraph = gr_begin + gr_missing + gr_fitline

  source =  ' SOURCE: s=userSource(id("graphdataset"))\n'

  data_x = ''
  data_y = ''
  data_color = ''
  data_size = ''
  guide_legend_color = ''
  guide_legend_size = ''
  scale_1 =   ''
  xCat = False
  yCat = False

  xCat,yCat=GetMeasLevel(spss,ChartXName,ChartYName)

  data = ' DATA: ' + ChartXName + '=col(source(s), name("' + ChartXName
  data_x = data + '"))\n'
  if xCat: data_x = data + '"),unit.category())\n'

  data = ' DATA: ' + ChartYName + '=col(source(s), name("' + ChartYName
  data_y = data + '"))\n'
  if yCat: data_y = data + '"),unit.category())\n'

  if ChartColorName != '':
    data_color = ' DATA: ' + ChartColorName + '=col(source(s), name("' + ChartColorName + '"), unit.category())\n'

  if ChartSizeName != '': # Should this always be 'unit category'??
    data_size = ' DATA: ' + ChartSizeName + '=col(source(s), name("' + ChartSizeName + '"), unit.category())\n'

  guide_x = f""" GUIDE: axis(dim(1), label({spssaux._smartquote(xlabel)}))\n"""
  guide_y = f""" GUIDE: axis(dim(2), label({spssaux._smartquote(ylabel)}))\n"""

  if ChartColorName != '':
    guide_legend_color = f""" GUIDE: legend(aesthetic(aesthetic.color.interior), label({spssaux._smartquote(color_label)}))\n"""

  if ChartSizeName != '':
    guide_legend_size = f""" GUIDE: legend(aesthetic(aesthetic.size), label({spssaux._smartquote(size_label)}))\n"""

  title_1 = ' GUIDE: text.title(label("' + chart_title + '"))\n'
  title_2 = ' GUIDE: text.footnote(label("' + chart_subtitle + '"))\n'
  title_3 = ' GUIDE: text.subfootnote(label("' + chart_footnote + '"))\n'

  el_x_y = ' ELEMENT: point(position(' + ChartXName + '*' + ChartYName

  if graph_type == "LINE":
    if ChartColorName == '':
      element_1 = el_x_y.replace('point(','line(') + '), missing.wings())\n'
    else:
      element_1 = el_x_y.replace('point(','line(') + '), color.interior(' + ChartColorName + '), missing.wings())\n'

  elif graph_type == "POINT":
    scale_1 =   ' SCALE: linear(dim(2), include(0))\n'
    if ChartColorName == '':
      element_1 = el_x_y + '))\n'
    else:
      element_1 = el_x_y + '), color.interior(' + ChartColorName + '))\n'

  elif graph_type == "BUBBLE":
    if ChartColorName == '':
      element_1 = el_x_y + '), size(' + ChartSizeName + '))\n'
    else:
      element_1 = el_x_y + '), color.interior(' + ChartColorName + '),size(' + ChartSizeName + '))\n'

  gpl = begin + source + data_x + data_y + data_color + data_size + guide_x + guide_y + \
    guide_legend_color + guide_legend_size + title_1 + title_2 + \
    title_3 + scale_1 + element_1 + end

  MakeGraph = ggraph + gpl
  
  return MakeGraph

def Make_SUMMARIZE (spssaux, SortBy, xname, sz_xname, sz_yname, sz_color, sz_size, ChartColorName, chart_title):

  sort_g = 'SORT CASES BY GVAR.\n'
  sort_x = sort_g.replace('GVAR',sz_xname)
  sort_grp = 'SORT CASES BY Group.\n'
  sz_cmd = 'SUMMARIZE /TABLES='

  if graph_type == "BUBBLE":
    if xname == "GVAR":
      if SortBy == "Group":
        sort = sort_grp
      else:
        sort = sort_g
      sz = sz_cmd + sz_xname + ' ' + sz_yname + ' BY GVAR BY ' + sz_size
    else:
      if SortBy == "Group":
        sort = sort_grp
      else:
        sort = sort_x
      sz = sz_cmd + sz_xname + ' ' + sz_yname + ' BY ' + sz_color + ' BY ' + sz_size
  else:
    if ChartColorName == '':
      if xname == "GVAR":
        if SortBy == "Group":
          sort = sort_grp
        else:
          sort = sort_g
        sz = sz_cmd + sz_yname + ' BY GVAR'
      else:
        if SortBy == "Group":
          sort = sort_grp
        else:
          sort = sort_x
        sz = sz_cmd + sz_yname + ' BY ' + sz_xname
    else:
      if color_name == "GVAR":
        if SortBy == "Group":
          sort = sort_grp
        else:
          sort = sort_g
        sz = sz_cmd + sz_yname + ' BY GVAR BY ' + sz_xname
      else:
        if SortBy == "Group":
          sort = sort_grp
        else:
          sort='SORT CASES BY ' + sz_color + ' ' + sz_xname + '.\n'
        sz = sz_cmd + sz_yname + ' BY ' + sz_color + ' BY ' + sz_xname

  sz_title = f""" /TITLE={spssaux._smartquote(chart_title)}"""
  summarize = "OMS SELECT TABLES /DESTINATION VIEWER=NO\n" + \
              " /IF COMMANDS='Summarize' SUBTYPES='Case Processing Summary' /TAG='_s_'.\n" + \
              sort  + sz + "\n /FORMAT=LIST NOCASENUM NOTOTAL /CELLS NONE /STATISTICS NONE\n" + \
              sz_title + ".\nOMSEND TAG='_s_'.\n"
              
  return summarize

def Make_VGRAPH (dim3, graph_type, k, xname, yname, color_name, size_name, ChartXName, ChartYName, ChartColorName, \
               ChartSizeName, xlabel, ylabel, color_label, size_label, chart_title, chart_subtitle, chart_footnote):

  if dim3:
    vgraph_syntax= 'VGRAPH\n' + \
     '  /GRAPHDATASET NAME="graphdataset" VARIABLES=x_name_here y_name_here color_name_here\n' + \
     '  /GRAPHSPEC SOURCE=INLINE.\n' + \
     'BEGIN GRAPHSRV\n' + \
     '{\n' + \
     '  "showValueLabels": true,\n' + \
     '  "usedFields": [\n' + \
     '    "x_name_here",\n' + \
     '    "y_name_here",\n' + \
     '    "color_name_here"\n' + \
     '  ],' + \
     '  "chartSettings": {\n' + \
     '    "type": "line",\n' + \
     '    "x": "x_name_here",\n' + \
     '    "y": "y_name_here",\n' + \
     '    "splitField": {\n' + \
     '  "name": "color_name_here",\n' + \
     '  "values": []\n' + \
     '    },\n' + \
     '    "title": "my_title_here",\n' + \
     '    "subtitle": "subtitle_here",\n' + \
     '    "footnote": "footnote_here",\n' + \
     '    "xAxisLabel": "x_label_here",\n' + \
     '    "yAxisLabel": "y_label_here",\n' + \
     '    "defaultTitleEnabled": true,\n' + \
     '    "filterNullValue": true,\n' + \
     '    "theme": "ibm_carbon_light_white",\n' + \
     '    "showValueLabels": true,\n' + \
     '    "__version": "2.6"\n' + \
     '  },\n' + \
     '  "options":{\n' + \
     '    "theme": ""\n' + \
     '  }\n' + \
     '}\n' + \
     'END GRAPHSRV.\n'

    vgraph=vgraph_syntax.replace('x_name_here',ChartXName).replace('y_name_here',ChartYName) \
      .replace('color_name_here',ChartColorName).replace('x_label_here',xlabel) \
      .replace('y_label_here',ylabel).replace('color_label_here',color_label) \
      .replace('my_title_here',chart_title).replace('subtitle_here',chart_subtitle) \
      .replace('footnote_here',chart_footnote)

  else:
    vgraph_syntax= 'VGRAPH\n' + \
     '  /GRAPHDATASET NAME="graphdataset" VARIABLES=x_name_here y_name_here\n' + \
     '  /GRAPHSPEC SOURCE=INLINE.\n' + \
     'BEGIN GRAPHSRV\n' + \
     '{\n' + \
     '  "showValueLabels": true,\n' + \
     '  "usedFields": [\n' + \
     '    "x_name_here",\n' + \
     '    "color_name_here"\n' + \
     '  ],' + \
     '  "chartSettings": {\n' + \
     '    "type": "line",\n' + \
     '    "x": "x_name_here",\n' + \
     '    "y": "y_name_here",\n' + \
     '    "title": "my_title_here",\n' + \
     '    "subtitle": "subtitle_here",\n' + \
     '    "footnote": "footnote_here",\n' + \
     '    "xAxisLabel": "x_label_here",\n' + \
     '    "yAxisLabel": "y_label_here",\n' + \
     '    "defaultTitleEnabled": true,\n' + \
     '    "filterNullValue": true,\n' + \
     '    "theme": "ibm_carbon_light_white",\n' + \
     '    "showValueLabels": true,\n' + \
     '    "__version": "2.6"\n' + \
     '  },\n' + \
     '  "options":{\n' + \
     '    "theme": ""\n' + \
     '  }\n' + \
     '}\n' + \
     'END GRAPHSRV.\n'

    vgraph=vgraph_syntax.replace('x_name_here',ChartXName).replace('y_name_here',ChartYName) \
      .replace('x_label_here',xlabel).replace('y_label_here',ylabel) \
      .replace('sub_title_here',chart_subtitle).replace('my_title_here',chart_title) \
      .replace('footnote_here',chart_footnote)

    return vgraph

def MakeVarLabel (COMMANDS,varname,varlabel):
  if varname != '' :
    nv=varlabel.replace('"','').replace("'",'')
    COMMANDS.append(f"""VARIABLE LABELS {varname} {spssaux._smartquote(nv)}.""")
    return

def RemoveKeyword (Cmd,TargetStr,RemoveStr,Orig):
  xlist = GetParameters(Cmd)
  found=[]
  begin_delete = -1
  end_delete = -1
  for i in xlist:
    if i == "ES" and Orig in ["ES_CONTRAST","ES_F","ES_ETA_SQUARED"]:
      FindMe = ' ' + Orig.replace("ES_","ES=").replace("ES=CONTRAST","ES=")
    else:
      FindMe = ' ' + i + '='
    num = str('{:003d}'.format(TargetStr.find(FindMe)))
    if int(num) != -1:
      if i == RemoveStr:
        found.append(num + '=' + "SKIP")
        begin_delete=int(num)
      else:
        found.append(num + '=' + i)
  found.sort()
  lastd = 0
  d = 0
  for f in found:
    lastd = d
    d = f[0:f.find('=')]
    if int(lastd) == int(begin_delete):
      end_delete=int(d)-1
      break
  if begin_delete > 0:
    if end_delete == -1: end_delete = len(TargetStr)
    T = (TargetStr[0:begin_delete] + TargetStr[end_delete+1:]).strip()
  else:
    T = TargetStr.strip()

  return T

def Rename (COMMANDS,varname,mystr,replace):
  global xname
  global xlabel
  global yname
  global ylabel
  global color_name
  global color_label
  global size_name
  global size_label

  if FindString(varname,mystr):
     n = varname.replace(mystr,replace)
     COMMANDS.append('RENAME VARIABLES (' + varname + '=' + n + ').')
     varname = n
  return varname

def helper():
  # open HTML help in default browser window.
  # The location is computed from the current module name.
  import webbrowser, os.path
  new = 2 # open in a new tab, if possible
  path = os.path.splitext(__file__)[0]
  # Mac: ~/Library/Application Support/IBM/SPSS Statistics/28/extensions/Power_Simulation_Extension/STATS_POWERSIM.html
  url = "file:///" + path.replace("STATS_POWERSIM",'').replace("\\\\","/").replace(" ","%20").replace("\\","/") + "Power_Simulation_Extension/STATS_POWERSIM.html"
  if not webbrowser.open(url,new=new): print(("Help file not found:" + url))

def Run(args):
  global print_debug
  global color_name
  global color_label
  global size_name
  global size_label
  global printback

  import spss
  printback = spss.GetSetting("PRINTBACK")
  if printback.upper() in ["YES","LISTING"]:
    spss.Submit("PRESERVE.\nSET PRINTBACK OFF.")

  args = args[list(args.keys())[0]]
  
  y=str(args).find("PRINT_DEBUG")
  print_debug = (y > 0)

  oobj = Syntax([
    Template("TYPE", subc="GRAPH", ktype="str", var="graph_type", vallist=["line","point","bubble","none"]),
    Template("PARAMETERS", subc="INPUT", ktype="str", var="parameter_statement"),
    Template("COMMAND", subc="INPUT", ktype="literal", var="command"),
    Template("VARY", subc="INPUT", ktype="literal", var="vary"),
    Template("VALUES", subc="INPUT", ktype="literal", var="values"),
    Template("TABLE", subc="OPTIONS", ktype="str", var="sz_table", vallist=["yes","no"]),
    Template("SPS", subc="OPTIONS", ktype="literal", var="my_syntax"),
    Template("OUTFILE", subc="OPTIONS", ktype="literal", var="outfile"),
    Template("X", subc="GRAPH", ktype="literal", var="xname"),
    Template("XLABEL", subc="GRAPH", ktype="literal", var="xlabel"),
    Template("Y", subc="GRAPH", ktype="literal", var="yname"),
    Template("YLABEL", subc="GRAPH", ktype="literal", var="ylabel"),
    Template("COLOR", subc="GRAPH", ktype="literal", var="color_name"),
    Template("COLOR_LABEL", subc="GRAPH", ktype="literal", var="color_label"),
    Template("SIZE", subc="GRAPH", ktype="literal", var="size_name"),
    Template("SIZE_LABEL", subc="GRAPH", ktype="literal", var="size_label"),
    Template("ENGINE", subc="GRAPH", ktype="str", var="gtype", vallist=["ggraph","vgraph"])])

  if print_debug:
    print("ARGS")
    print(args)

  if "HELP" in args:
    helper()
  else:
    processcmd(oobj,args,do_power)

def SetTableCaption(szcmd, caption1, caption2):
  import SpssClient
  SpssClient.StartClient()
  SpssClient.RunSyntax(szcmd)
  OutputDoc = SpssClient.GetDesignatedOutputDoc()
  OutputItemList = OutputDoc.GetOutputItems()
  NumItems=OutputItems.Size()
  j = 0
  #for index in range(NumItems):
  #  OutputItem = OutputItemList.GetItemAt(index)
  #  if OutputItem.GetType() == SpssClient.OutputItemType.PIVOT:
  #    CmdID = OutputItem.GetProcedureName().upper()
  #    if CmdID == "SUMMARIZE": j = index #get the last summarize report table
  #if j > 0:
  #  OutputItem = OutputItemList.GetItemAt(j)
  #  PivotTable = OutputItem.GetSpecificType()
  #  Title=PivotTable.GetTitleText()
  #  caption=caption1 + '\n' + caption2
  #  PivotTable.SetCaptionText(caption)
  SpssClient.StopClient()

def WarningsTable(Text):
  import spss
  spss.StartProcedure("STATS_POWERSIM")
  table = spss.BasePivotTable("Warnings ","Warnings")
  table.Append(spss.Dimension.Place.row,"rowdim",hideLabels=True)
  rowLabel = spss.CellText.String("1")
  table[(rowLabel,)] = spss.CellText.String(Text)
  spss.EndProcedure()

def Get_UI_Lang(my_os):
  ## Get ui_language
  
  UI_Lang="English"  ## Default assumption
  
  if my_os == "darwin":
    import plistlib
    import os
    import getpass
    username=getpass.getuser()
    fn = '/Users/' + username + '/Library/Preferences/com.ibm.spss.plist'
    if not os.path.exists(fn):
      print(fn)
      print("Can't find com.ibm.spss.plist.")
    else:
      with open(fn, 'rb') as f:  
        pl = plistlib.load(f)
        x=str(pl)
        y=x.index("ui_language")
        z=x.index(",",y+1)
        UI_Lang=x[y+13:z].replace("'","").replace(' ',"")
   
  elif my_os == "windows":
    import winreg
    path= winreg.HKEY_CURRENT_USER
    key = winreg.OpenKeyEx(path, r"Software\JavaSoft\Prefs\com\ibm\/S/P/S/S\/Statistics\one\ui\options\general")
    value = winreg.QueryValueEx(key,"ui_language")
    if key: winreg.CloseKey(key)
    UI_Lang=str(value[0]).replace("/","")

  return(UI_Lang)

def GetSyntaxFromUI(lang,command):
  import SpssClient
  SpssClient.StartClient()
  ActiveDataDoc = SpssClient.GetActiveDataDoc()
  SpssDataUI = ActiveDataDoc.GetDataUI()

  c=command.upper()
  l=lang.upper()
  
  if FindString(c, "POWER MEANS ONESAMPLE"): power=1
  elif FindString(c, "POWER MEANS RELATED"): power=2
  elif FindString(c, "POWER MEANS INDEPENDENT"): power=3
  elif FindString(c, "POWER ONEWAY ANOVA"): power=0
  elif FindString(c, "POWER PROPORTIONS ONESAMPLE"): power=5
  elif FindString(c, "POWER PROPORTIONS RELATED"): power=4
  elif FindString(c, "POWER PROPORTIONS INDEPENDENT"): power=6
  elif FindString(c, "POWER PEARSON ONESAMPLE"): power=7
  elif FindString(c, "POWER SPEARMAN ONESAMPLE"): power=9
  elif FindString(c, "POWER PARTIALCORR"): power=8
  elif FindString(c, "POWER UNIVARIATE LINEAR"): power=10
  else: power=1
  
  BPORTUGU=["Médias>Análise de Variância Unidirecional","Médias>Teste-T de uma amostra","Médias>Teste-T de amostras pareadas",\
  "Médias>Teste-T de amostras independentes","Proporções>Teste binomial de amostras relacionadas",\
  "Proporções>Teste binomial de uma amostra","Proporções>Teste binomial de amostras independentes",\
  "Correlações>Momento de produto Pearson","Correlações>Parcial","Correlações>Ordem de posto do Spearman",\
  "Regressão>Linear univariado"]
  ENGLISH=["Means>One-Way ANOVA","Means>One-Sample T Test","Means>Paired-Samples T Test","Means>Independent-Samples T Test",\
  "Proportions>Related-Samples Binomial Test","Proportions>One-Sample Binomial Test","Proportions>Independent-Samples Binomial Test",\
  "Correlations>Pearson Product-Moment","Correlations>Partial","Correlations>Spearman Rank-Order","Regression>Univariate Linear"]
  FRENCH=["Moyennes>ANOVA à 1 facteur","Moyennes>Test T pour échantillon unique","Moyennes>Test T pour échantillons appariés",\
  "Moyennes>Test T pour échantillons indépendants","Proportions>Test binomial pour échantillons liés",\
  "Proportions>Test binomial pour échantillon unique","Proportions>Test binomial d'échantillons indépendants",\
  "Corrélations>Produit-moment de Pearson","Corrélations>Partielle","Corrélations>Ordre des rangs de Spearman",\
  "Régression>Linéaire univarié"]
  GERMAN=["Mittelwerte>Einfaktorielle Varianzanalyse","Mittelwerte>t-Test bei einer Stichprobe",\
  "Mittelwerte>t-Test bei Stichproben mit paarigen Werten","Mittelwerte>t-Test bei unabhängigen Stichproben",\
  "Anteile>Test auf Binomialverteilung bei verbundenen Stichproben","Anteile>Test auf Binomialverteilung bei einer Stichprobe",\
  "Anteile>Test auf Binomialverteilung bei unabhängigen Stichproben","Korrelationen>Pearson-Produkt-Moment",\
  "Korrelationen>Partiell","Korrelationen>Spearman-Rangordnung","Regression>Univariat linear"]
  ITALIAN=["Medie>ANOVA a una via","Medie>Test T a campione singolo","Medie>Test T a campioni accoppiati",\
  "Medie>Test T a campioni indipendenti","Proporzioni>Test binomiale a campioni correlati",\
  "Proporzioni>Test binomiale a campione singolo","Proporzioni>Test binomiale a campioni indipendenti",\
  "Correlazioni>PPMC (Pearson Product-Moment Correlation)","Correlazioni>Parziale","Correlazioni>Ordine di rango di Spearman",\
  "Regressione>Lineare univariata"]
  JAPANESE=["平均(M)>一元配置分散分析(A)","平均(M)>1 サンプルの t 検定(O)","平均(M)>対応のあるサンプルの t 検定(P)",\
  "平均(M)>独立したサンプルの t 検定(I)","比率(P)>対応サンプルによる 2 項検定(R)","比率(P)>1 サンプルによる 2 項検定(O)",\
  "比率(P)>独立サンプルによる 2 項検定(I)","相関(C)>Pearson の積率(M)","相関(C)>偏相関(P)","相関(C)>Spearman ランク順(S)",\
  "回帰分析(R)>1 変量の線型回帰(U)"]
  KOREAN=["평균(M)>일원배치 분산분석(A)","평균(M)>일표본 T 검정(O)","평균(M)>대응표본 T 검정(P)","평균(M)>독립표본 T 검정(I)",\
  "비율(P)>대응표본 이항검정(R)","비율(P)>일표본 이항 검정(O)","비율(P)>독립표본 이항검정(I)","상관관계(C)>Pearson 적률(M)",\
  "상관관계(C)>편상관(P)","상관관계(C)>Spearman 순위-순서(S)","회귀(R)>일변량 선형(U)"]
  POLISH=["Średnie>Jednoczynnikowa ANOVA","Średnie>Test t dla jednej próby","Średnie>Test t dla prób zależnych",\
  "Średnie>Test t dla prób niezależnych","Proporcje>Test dwumianowy dla prób zależnych",\
  "Proporcje>Test dwumianowy dla jednej próby","Proporcje>Test dwumianowy dla prób niezależnych","Korelacje>Pearsona…",\
  "Korelacje>Cząstkowe…","Korelacje>Spearmana…","Regresja>Liniowa jednej zmiennej…"]
  RUSSIAN=["Средние>Однофакторный дисперсионный анализ","Средние>Одновыборочный T-критерий",\
  "Средние>T-критерий для парных выборок","Средние>T-критерий для независимых выборок",\
  "Доли>Биномиальный критерий для связанных выборок","Доли>Одновыборочный биномиальный критерий",\
  "Доли>Биномиальный критерий для независимых выборок","Корреляции>Смешанный момент Пирсона","Корреляции>Частная",\
  "Корреляции>Коэффициент ранговой корреляции Спирмена","Регрессия>Линейная одномерная"]
  SPANISH=["Medias>ANOVA de un factor","Medias>Prueba T de una muestra","Medias>Prueba T de muestras emparejadas",\
  "Medias>Prueba T de muestras independientes","Proporciones>Prueba binomial para muestras relacionadas",\
  "Proporciones>Prueba binomial para una muestra","Proporciones>Prueba binomial para muestras independientes",\
  "Correlaciones>Momento-producto de Pearson","Correlaciones>Parcial","Correlaciones>Orden de rangos de Spearman",\
  "Regresión>Lineal univariado"]
  SCHINESE=["均值(M)>单因素 ANOVA 检验","均值(M)>单样本 t 检验(O)","均值(M)>成对样本 t 检验(P)","均值(M)>独立样本 t 检验(I)",\
  "比例(P)>相关样本二项检验(R)","比例(P)>单样本二项检验(O)","比例(P)>独立样本二项检验(I)","相关性(C)>皮尔逊积矩(M)","相关性(C)>偏相关性(P)",\
  "相关性(C)>斯皮尔曼秩次(S)","回归(R)>单变量线性(U)"]
  TCHINESE=["平均值(M)>單因數變異數分析(A)","平均值(M)>單樣本 T 檢定(O)","平均值(M)>成對樣本 T 檢定(P)","平均值(M)>獨立樣本 T 檢定(I)",\
  "比例(P)>相關樣本二項式檢定(R)","比例(P)>單樣本二項式檢定(O)","比例(P)>獨立樣本二項式檢定(I)","相關性(C)>Pearson 積差(M)",\
  "相關性(C)>偏相關(P)","相關性(C)>Spearman 等級","迴歸(R)>單變量線性(U)"]

  if l == "BPORTUGU": 
    Menu="Analisar>Análise de potência"
    cmdname=BPORTUGU[power]
  elif l == 'ENGLISH':
    Menu="Analyze>Power Analysis"
    cmdname=ENGLISH[power]
  elif l == 'FRENCH':
    Menu="Analyse>Analyse de puissance"
    cmdname=FRENCH[power]
  elif l == 'GERMAN':
    Menu='Analysieren>Poweranalyse'
    cmdname=GERMAN[power]
  elif l == "ITALIAN":
    Menu='Analizza>Analisi di potenza'
    cmdname=ITALIAN[power]
  elif l == "JAPANESE":
    Menu='分析(A)>検定力分析(W)'
    cmdname=JAPANESE[power]
  elif l == "KOREAN":
    Menu='분석(A)>거듭제곱 분석(W)'
    cmdname=KOREAN[power]
  elif l == "POLISH":
    Menu='Analiza>Moc testów'
    cmdname=POLISH[power]
  elif l == "RUSSIAN":
    Menu='Анализ>Анализ статистической мощности'
    cmdname=RUSSIAN[power]
  elif l == "SPANISH":
    Menu='Analizar>Análisis de potencia'
    cmdname=SPANISH[power]
  elif l == "SCHINESE":
    Menu='分析(A)>功效分析(W)'
    cmdname=SCHINESE[power]
  elif l == "TCHINESE":
    Menu='分析(A)>檢定力分析(W)'
    cmdname=TCHINESE[power]

  import spss
  x = SpssDataUI.InvokeDialog(Menu+">"+cmdname,False)
  syntax=x.replace(' =','=').replace('= ','=')
  return syntax

def do_power(graph_type='',parameter_statement='',command='',vary='',values='',sz_table='',\
             my_syntax='',outfile='',xname='',xlabel='',yname='',ylabel='',color_name='',\
             color_label='',size_name='',size_label='',gtype="GGRAPH"):

  import spss
  import spssaux

  global printback
  
  MyLanguage=spss.GetSetting("OLANG","").upper()
  if MyLanguage == '': MyLanguage = "ENGLISH"
  
  #Set up defaults for string values of VARY
  if values == '':
    if vary == "TEST":
      values = "NONDIRECTIONAL DIRECTIONAL"
    elif vary == "METHOD":
      values = "CHISQ T LRT FISHER"
    elif vary == "ESTIMATE":
      values = "NORMAL BINOMIAL"
    elif vary in ["ADJUST_BIAS","CONTINUITY","POOLED","INTERCEPT"]:
      values = "TRUE FALSE"
    elif vary == "VARIANCE":
      values = "BW FHP CC"
    elif vary == "MODEL":
      values = "FIXED RANDOM"
 
  if graph_type == '': graph_type="LINE"
  if gtype == '': gtype="GGRAPH"
  if sz_table == '': sz_table="YES"
  graph_type = graph_type.upper()
  command = command.upper().replace('_',' ')
  if parameter_statement != '': parameter_statement = " /PARAMETERS " + parameter_statement.upper()
  vary = vary.upper()
  if xname != '': xname = xname.upper()
  if yname != '':
    yname = yname.upper()
  else:
    yname = "_EMPTY_"
  if color_name != '': color_name = color_name.upper()
  if size_name != '': size_name = size_name.upper()
  if sz_table != '': sz_table=sz_table.upper()
  gtype = gtype.upper()
  if xname == "VARY_VALUES": xname = vary
  if xname == "NONE": xname = ''
  if yname == "VARY_VALUES": yname = vary
  if yname == "NONE": yname = ''
  if color_name == "VARY_VALUES": color_name = vary
  if color_name == "NONE": color_name = ''
  if size_name == "VARY_VALUES": size_name = vary
  if size_name == "NONE": size_name = ''
  if my_syntax == "NONE": my_syntax = ''
  if outfile == "NONE": outfile = ''
  SearchingForSampleSize = False
  ChartXName = ''
  ChartYName = ''
  ChartColorName = ''
  ChartSizeName = ''
  sz_xname=ChartXName
  sz_yname=ChartYName
  sz_color=ChartColorName
  sz_size=ChartSizeName
  Names=[]
  Labels=[]
  Chart=[]
  Sz=[]
  LinRegPartialCorr = False
  errorNum = '0'

  if vary == '' or values == '' or command == '':
    WarningsText="COMMAND, VARY, and VALUES are all required. At least one is missing. This procedure cannot run."
    WarningsTable(WarningsText)
    errorNum = '3'
  else:
    if print_debug:
      print("type="+graph_type)
      print("parameter_statement="+parameter_statement)
      print("command="+command)
      print("vary="+vary)
      print("values="+values)
      print("table="+sz_table)
      print("syntax="+my_syntax)
      print("outfile="+outfile)
      print("xname="+xname)
      print("xlabel="+xlabel)
      print("yname="+yname)
      print("ylabel="+ylabel)
      print("color_name="+color_name)
      print("color_label="+color_label)
      print("size_name="+size_name)
      print("size_label="+size_label)
      print("gtype="+gtype)

    if parameter_statement == '':
      Lang=Get_UI_Lang(PLATFORM)
      syntax=GetSyntaxFromUI(Lang,command)
    else:
      syntax = command + " " + parameter_statement.upper().replace('  /',' /')

    Contrast_ES = False
    x = KeepSyntax(syntax,"PARAMETERS").replace(command,'')
    if vary in ["ES_F","ES_ETA_SQUARED"]:
      tvary = "ES"
    else:
      tvary=vary
    temp=x
    if temp.find(' ' + tvary + '=') > -1:
      x = RemoveKeyword(command, temp, tvary, vary)
    if FindString(command,"ONEWAY"):
      y = KeepSyntax(syntax,"CONTRAST").replace(command,'')
      if FindString(y,"ES"):
        Contrast_ES = True
        if vary == "ES_CONTRAST": tvary = "ES"
        temp=y.replace(command,'').strip()
        if temp.find(' ' + tvary + '=') > -1:
          y = RemoveKeyword(command, temp, tvary, vary)
      x = x + ' ' + y

    x = command + ' ' + x
    if print_debug: print("Kept Syntax: "+x)

    if x == '':
      WarningsTable("Power Analysis cannot be run; analysis abandoned or otherwise empty.")
      errorNum = '3'
    else:
      if print_debug: print("Syntax to be run: " + x)

      LinRegPartialCorr = x.lower().find("partial_corr") > -1
      PowerCommand=x.strip().upper()
      if PowerCommand.endswith('.'): PowerCommand=PowerCommand[0:len(PowerCommand)-1]

      SearchingForSampleSize = (PowerCommand.upper().count("POWER") == 2)

      N_on_Y = False
      N_on_Y = SearchingForSampleSize

      # Some VARY keyword values in this extension need to be mapped to the right
      # POWER keyword

      if FindString(PowerCommand,"POWER MEANS RELATED") or \
         FindString(PowerCommand,"POWER PROPORTIONS RELATED"):
         if vary.upper() == "N": vary = "NPAIRS"

      #Probably the same will be needed for SD (POOLED_SD in at least one)

      if print_debug: print("Power command="+PowerCommand)

      ActiveDataset = ''
      chart_title = ''
      chart_subtitle = ''
      chart_footnote = ''
      vgraph_syntax = ''
      vgraph = ''
      MakeData=[]
      MakeGraph=[]
      PowerVars = []
      target_dsn = "my_temp_sav_file"
      dim2 = False
      dim3 = False
      no_graph = False

      values=values.replace('"',"'").replace("' '",'|').replace("'",'')

      if values.find("|") > -1:
        testvals=values.split("|")
      else:
        testvals=values.split(" ")

      ## SET SOME CHART DEFAULTS
      ## If x is empty and the user has power in the PARAMETERS, put Power in X.
      if graph_type != "NONE":
        if xname == '':
          if SearchingForSampleSize:
            xname = "Power"
            yname = "N"
          else:
            xname = "N"
            yname = "Power"

      no_graph = (graph_type == "NONE")
      dim2 = (color_name == '')
      dim3 = (xname != '' and yname != '' and color_name != '')

      if size_name != '' and graph_type in ["LINE","POINT"]:
        WarningsTable("For LINE or POINT charts, the SIZE parameter is ignored.")

      ############# Create data

      fh = ''
      dsn_closed = True
      dsn_closed = CloseData (target_dsn)

      if not dsn_closed:
        fh = 'DATASET CLOSE ' + target_dsn + '.\nNEW FILE.\nDATASET NAME ' + target_dsn + '.\n'
      else:
        fh = 'DATASET DECLARE ' + target_dsn + '.'

      if Contrast_ES:
        SubTypes = '["Contrast Test"]'
      else:
        SubTypes = '["Power Analysis Table"]'

      MakeData = []
      MakeData.append(fh + '\nPRESERVE.\nSET OLANG=English /PRINTBACK NONE.\n' + \
       'OMS /SELECT ALL EXCEPT=[WARNINGS] /DESTINATION VIEWER=NO /TAG="_n_".\nOMS' + \
       ' /SELECT TABLES /IF SUBTYPES=' + SubTypes + \
       ' /DESTINATION FORMAT=SAV OUTFILE=' + target_dsn + ' /TAG="_p_".')

      root_cmd = PowerCommand

      es_type = "NONE"
      if vary[0:3] == "ES_":
        if vary == "ES_F":
          es_type = "F(_VAL_)"
        elif vary == "ES_CONTRAST":
          es_type = "_VAL_"
        elif vary == "ES_ETA_SQUARED":
          es_type = "ETA_SQUARED(_VAL_)"

        if es_type != "NONE": vary = "ES"

        l=len(testvals)
        for i in range(l):
          testvals[i]=es_type.replace("_VAL_",testvals[i])

      for v in testvals:
        if str(v).strip() == '':
          testvals.remove(v)
        else:
          cmd = root_cmd + ' ' + vary.strip() + '=' + str(v).replace("'",'').replace('"','').strip() + '.'
          if print_debug: print("CMD="+cmd)
          MakeData.append(cmd)

      MakeData.append('OMSEND TAG=["_p_","_n_"].\nRESTORE.\nDATASET ACTIVATE ' + target_dsn + ' WINDOW=ASIS.')
      MakeData.append('DELETE VARIABLES Command_ TO Label_.')

      if outfile != '':
        MakeData.append('DATASET COPY MyTempCopy.')
        MakeData.append('DATASET ACTIVATE MyTempCopy WINDOW=ASIS.')
        MakeData.append(f"""SAVE OUTFILE={spssaux._smartquote(outfile)}.""")
        MakeData.append('DATASET CLOSE MyTempCopy.')
        MakeData.append('DATASET ACTIVATE ' + target_dsn + ' WINDOW=ASIS.')

      #####
      # Map VARY to the right varname produced by Power.
      #####

      c=PowerCommand.upper()
      k=vary.upper().strip()
      SortBy = ''

      if no_graph:
        xname = k
        yname = "Power"
        if dim3: color_name = "N"

      Names=[xname.upper(),yname.upper(),color_name.upper(),size_name.upper()]

      # SPSS makes variables with names based on keywords
      j = 0
      for i in Names:
        if Names[j] in ["ES_CONTRAST","ES_ETA_SQUARED","ES_F"]: Names[j] = "EffectSize"
        if Names[j] == "SIGNIFICANCE": Names[j] = "Sig"
        if Names[j] == "PARTIALOUT": Names[j] = "Partialled"
        if Names[j] == "PARTIAL_CORR": Names[j] = "Partial"
        if Names[j] == "RHO": Names[j] = "EffectSize"
        if Names[j] == "SD": Names[j] = "Std.Dev"
        if Names[j] == "NPAIRS": Names[j] = "N"
        if LinRegPartialCorr:
          if Names[j] == "TOTAL_PREDICTORS": Names[j] = "Total"
          if Names[j] == "TEST_PREDICTORS": Names[j] = "Test"
        else:
          if Names[j] == "TOTAL_PREDICTORS": Names[j] = "Full"
          if Names[j] == "TEST_PREDICTORS": Names[j] = "Nested"
        if Names[j] == "FULL_MODEL": Names[j] = "Full_A"
        if Names[j] == "NESTED_MODEL": Names[j] = "Nested_A"
        if Names[j] == "POWER": MakeData.append("VARIABLE LEVEL Power (ORDINAL).")
        j = j + 1

      ChartXName=Rename(MakeData,Names[0],'.','_')
      ChartYName=Rename(MakeData,Names[1],'.','_')
      ChartColorName=Rename(MakeData,Names[2],'.','_')
      ChartSizeName=Rename(MakeData,Names[3],'.','_')
      Chart=[ChartXName,ChartYName,ChartColorName,ChartSizeName]

      xname=Names[0]
      yname=Names[1]
      color_name=Names[2]
      size_name=Names[3]
      sz_xname=Chart[0]
      sz_yname=Chart[1]
      sz_color=Chart[2]
      sz_size=Chart[3]
      Sz=[sz_xname,sz_yname,sz_color,sz_size]
      Labels=[xlabel,ylabel,color_label,size_label]

      if k == "SIGNIFICANCE": k = "SIG"

      if print_debug:
        print("Chart Names:")
        print("Number of valid chart entries: " + str(len(Chart)))
        print('x=' + Chart[0] + ', y=' + Chart[1] + ', color=' + Chart[2] + ', size=' + Chart[3])
        print(k)

      if FindString(c,"POWER MEANS INDEPENDENT") or FindString(c,"POWER PROPORTIONS INDEPENDENT"):
        x=Names[0].lower()
        y=Names[1].lower()
        color=Names[2].lower()
        size=Names[3].lower()
        ns = ['n1','n2']
        if x not in ns and y not in ns:
          t='COMPUTE TotalN=N1+N2.\nFORMATS TotalN (F16).\nEXECUTE.'
          j = 0
          for i in Names:
            if FindString(i.lower(),'totaln') or FindString(i.lower(),'n'):
              Chart[j]="TotalN"
              Sz[j]=Chart[j]
              Labels[j]="Total Number of Cases"
              MakeData.append(t)
            j = j + 1
        if print_debug: print("Finished " + c)

      if k == "TEST":
        MakeData.append('STRING GVAR (A9).\nSORT CASES BY Var1.')
        i1 = values.upper().find("NON")
        i2 = values.upper().find("DIR")
        if i1 < i2:
          MakeData.append('IF MOD($CASENUM,2) = 0 GVAR = "1-Tailed".')
          MakeData.append('IF MOD($CASENUM,2) = 1 GVAR = "2-Tailed".')
        else:
          MakeData.append('IF MOD($CASENUM,2) = 0 GVAR = "2-Tailed".')
          MakeData.append('IF MOD($CASENUM,2) = 1 GVAR = "1-Tailed".')

        MakeData.append('SORT CASES BY GVAR.')
        SortBy = "GVAR"
        Chart,Sz,Labels = AssignVarName(k,Names,Chart,Sz,Labels,SortBy)
        if print_debug: print("Finished k = " + k)

      elif k == "ADJUST_BIAS":
        MakeData.append('STRING GVAR (A13).\nSORT CASES BY Var1.')
        i1 = values.upper().find("TRU")
        i2 = values.upper().find("FAL")
        if i1 < i2:
          MakeData.append('if mod($casenum,2) = 0 GVAR = "Adjust".\nif mod($casenum,2) = 1 GVAR = "Do not adjust".')
        else:
          MakeData.append('if mod($casenum,2) = 0 GVAR = "Do not adjust".\nif mod($casenum,2) = 1 GVAR = "Adjust".')

        MakeData.append('SORT CASES BY GVAR.')
        SortBy = "GVAR"
        Chart,Sz,Labels = AssignVarName(k,Names,Chart,Sz,Labels,SortBy)
        if print_debug: print("Finished k = " + k)

      elif k == "METHOD":
        CreateGroupingVariable(MakeData,"Var1",'Group',testvals)
        MakeData.append('SORT CASES BY Group.')
        SortBy = "Group"
        Chart,Sz,Labels = AssignVarName(k,Names,Chart,Sz,Labels,"GVAR")
        if print_debug: print("Finished k = " + k)

      elif k in ["VARIANCE","CORRELATION","TOTAL_PREDICTORS","TEST_PREDICTORS",\
                 "FULL_MODEL","NESTED_MODEL","POOLED_SD","N","ESTIMATE","CONTINUITY",\
                 "POOLED","PROPORTIONS","MODEL","SIG","INTERCEPT","PARTIAL_CORR",\
                 "ALTERNATIVE","MEAN","NULL","GROUP_MEANS","MEANS","RHO","SD",\
                 "GROUP_SIZES","GROUP_WEIGHTS","ES"]:
        CreateGroupingVariable(MakeData, "Var1",'Group',testvals)
        Chart,Sz,Labels = AssignVarName(k,Names,Chart,Sz,Labels,"GVAR")

        k1 = ''
        if k == "TOTAL_PREDICTORS":
          k1 = "TOTAL"
        elif k == "TEST_PREDICTORS":
          k1 = "TEST"
        elif k == "INTERCEPT":
          k1 = "GVAR"
        elif k == "PARTIAL_CORR":
          k1 = "PARTIAL"
        elif k == "FULL_MODEL":
          if LinRegPartialCorr:
            k1 = "FULL"
          else:
            k1 = "FULL_A"
        elif k == "NESTED_MODEL":
          if LinRegPartialCorr:
            k1 = "NESTED"
          else:
            k1 = "NESTED_A"
        else:
          k1 = k

        for j in range(0,len(Chart)):
          if Chart[j].upper() == k1:
            Chart[j] = "GVAR"
            break

        SortBy = "Group"
        if print_debug: print("Finished k = " + k)

      elif k == "NRATIO":
        MakeData.append('SORT CASES BY Var1.')
        count = 1
        for v in testvals:
          MakeData.append('IF Var1=' + str(count).strip() + ' GVAR=' + str(v).strip() + '.')
          count = count + 1

        SortBy = "GVAR"
        MakeData.append('SORT CASES BY GVAR.')

        j = 0
        if dim3: j = 2
        Chart[j]="GVAR"
        Sz[j]=Chart[j]
        if Chart[j] != '': MakeData.append('VARIABLE LEVEL ' + Chart[j] + ' (NOMINAL).')

      if print_debug: print("Finished k = " + k)

      xname = Names[0]
      yname = Names[1]
      color_name = Names[2]
      size_name = Names[3]
      ChartXName = Chart[0]
      ChartYName = Chart[1]
      ChartColorName = Chart[2]
      ChartSizeName = Chart[3]
      sz_xname = Sz[0]
      sz_yname = Sz[1]
      sz_color = Sz[2]
      sz_size = Sz[3]
      xlabel = Labels[0]
      ylabel = Labels[1]
      color_label = Labels[2]
      size_label = Labels[3]

      MakeVarLabel (MakeData,ChartXName,xlabel)
      MakeVarLabel (MakeData,ChartYName,ylabel)
      MakeVarLabel (MakeData,ChartColorName,color_label)
      MakeVarLabel (MakeData,ChartSizeName,size_label)
      if print_debug:
        print("Error Number=" + errorNum + ".")
        print("Finished Making Variable Labels")

      ##### END MAKING DATA #####

  if errorNum != '3':

    try:
      if print_debug: print("Begin Submitting Data to make Chart")
      spss.Submit(MakeData)
      if print_debug: print("End Submitting Data to make Chart")
    except:
      errorNum = ErrorChecking(spss, "Creating commands")

  if errorNum != '3':

    PVarLabels = []

    try:
      if target_dsn != "":
        spss.StartDataStep()
        datasetObj = spss.Dataset(target_dsn)
        varListObj = datasetObj.varlist
        for var in datasetObj.varlist:
          PowerVars.append(var.name)
          varObj = datasetObj.varlist[var.name]
          PVarLabels.append(varObj.label)
        spss.EndDataStep()
        if print_debug: print("Finished Reading Variable Names and Labels")
    except:
      errorNum = ErrorChecking(spss,"Getting variable information from the newly created data")

    for var in PowerVars:
      if var in ["POWER","ACTUALPOWER","N","N1","N2"]: spss.Submit("VARIABLE LEVEL " + var + " (SCALE).")

  if errorNum != '3':

    if print_debug:
      print(PowerVars)
      print(PVarLabels)

    ### MAKE GRAPH TITLES ###

    if xlabel == '': xlabel = ChartXName
    if ylabel == '': ylabel = ChartYName
    if color_label == '': color_label = ChartColorName
    if size_label == '': size_label = ChartSizeName

    if ChartXName == "GVAR": xlabel = vary.upper()
    if ChartYName == "GVAR": ylabel = vary.upper()
    if ChartColorName == "GVAR": color_label = vary.upper()
    if ChartSizeName == "GVAR": size_label = vary.upper()

    varying = vary + "(" + values + ")"
    gridlines=''

    chart_title = ylabel.upper() + ' by ' + xlabel.upper()
    if dim3: chart_title = chart_title + ' by ' + color_label.upper()
    chart_title = command + ": " + chart_title
    chart_subtitle = PowerCommand.upper().replace(command,'').replace('\n','').replace("/PARAMETERS",'').strip()
    chart_footnote = varying.upper()

    if print_debug:
      print("X="+ChartXName)
      print("Y="+ChartYName)
      print("COLOR="+ChartColorName)
      print("SIZE="+ChartSizeName)
      print("GRAPH TYPE="+graph_type)

    ### MAKE GRAPH SYNTAX ###

    if FindString(gtype.lower(),"vgraph"):
      vgraph = Make_VGRAPH (dim3, graph_type, k, xname, yname, color_name, size_name, ChartXName, ChartYName, ChartColorName, \
               ChartSizeName, xlabel, ylabel, color_label, size_label, chart_title, chart_subtitle, chart_footnote)
    elif FindString(gtype.lower(),"ggraph"):
      MakeGraph = Make_GGRAPH (graph_type, k, xname, yname, color_name, size_name, ChartXName, ChartYName, ChartColorName, \
                  ChartSizeName, xlabel, ylabel, color_label, size_label, chart_title, chart_subtitle, chart_footnote)

    ### MAKE SUMMARIZE SYNTAX ###

    summarize = Make_SUMMARIZE (spssaux, SortBy, xname, sz_xname, sz_yname, sz_color, sz_size, ChartColorName, chart_title)

    SPS = ''
    SPS_PATH,SPS_NAME=path_leaf(my_syntax)
    line_sep = '\n****************.\n'

    ### WRITE SYNTAX TO FILE IF REQUESTED ###

    if my_syntax != '':
      os.makedirs(os.path.dirname(SPS_PATH), exist_ok=True)
      SPS = open(my_syntax, mode='w', encoding='utf-8')
      for m in MakeData:
        SPS.write(m+'\n')
      SPS.write(line_sep + str(summarize) + line_sep + str(MakeGraph) + "\n")
      SPS.close()

    if print_debug:
      for m in MakeData:
        print(m)
      print(line_sep + str(summarize) + line_sep + str(MakeGraph) + "\n")

    ### DISPLAY TABLE IF REQUESTED ###

  if errorNum != '3':
    if sz_table == "YES":
      try:
        spss.Submit(summarize)
      except:
        errorNum = ErrorChecking(spss, "Submitting this syntax: " + summarize)

    ### DISPLAY GRAPH IF REQUESTED ###

  if errorNum != '3':
    if not no_graph:
      try:
        spss.Submit(MakeGraph)
      except:
        errorNum = ErrorChecking(spss,"Making graph: " + MakeGraph)

  if printback.upper() in ["YES","LISTING"]: spss.Submit("PRESERVE.\nSET PRINTBACK OFF.")
