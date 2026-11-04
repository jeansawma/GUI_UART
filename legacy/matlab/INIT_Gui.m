function varargout = INIT_Gui(varargin)
% INIT_GUI MATLAB code for INIT_Gui.fig
%      INIT_GUI, by itself, creates a new INIT_GUI or raises the existing
%      singleton*.
%
%      H = INIT_GUI returns the handle to a new INIT_GUI or the handle to
%      the existing singleton*.
%
%      INIT_GUI('CALLBACK',hObject,eventData,handles,...) calls the local
%      function named CALLBACK in INIT_GUI.M with the given input arguments.
%
%      INIT_GUI('Property','Value',...) creates a new INIT_GUI or raises the
%      existing singleton*.  Starting from the left, property value pairs are
%      applied to the GUI before INIT_Gui_OpeningFcn gets called.  An
%      unrecognized property name or invalid value makes property application
%      stop.  All inputs are passed to INIT_Gui_OpeningFcn via varargin.
%
%      *See GUI Options on GUIDE's Tools menu.  Choose "GUI allows only one
%      instance to run (singleton)".
%
% See also: GUIDE, GUIDATA, GUIHANDLES

% Edit the above text to modify the response to help INIT_Gui

% Last Modified by GUIDE v2.5 20-Mar-2022 21:00:14

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @INIT_Gui_OpeningFcn, ...
                   'gui_OutputFcn',  @INIT_Gui_OutputFcn, ...
                   'gui_LayoutFcn',  [] , ...
                   'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT


% --- Executes just before INIT_Gui is made visible.
function INIT_Gui_OpeningFcn(hObject, eventdata, handles, varargin)
% This function has no output args, see OutputFcn.
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% varargin   command line arguments to INIT_Gui (see VARARGIN)

% Choose default command line output for INIT_Gui
handles.output = hObject;

instrreset
global ser nbdata exit conn
exit = 0;
nbdata = 2030;
conn = 0;

global vec_old
vec_old = [];

set(handles.listbox1,'String',seriallist);
set(handles.figure1, 'WindowKeyPressFcn', @KeyPress);

axes(handles.axes1);

global var mode Dvar
var = zeros(15,25);
mode = 0;
Dvar = "";
for i=1:15
    for j=1:25
        Dvar(i,j)="";
    end
end

global Plot_Mask Plot_i Plot_j Pmax
Pmax=15;
Plot_Mask = zeros(Pmax,1);
Plot_i = zeros(Pmax,1);
Plot_j = zeros(Pmax,1);
global Tsp
Tsp = 0.2;
 handles.timer = timer('Name','MyTimer',               ...
                       'Period',Tsp,                    ... 
                       'StartDelay',1,                 ... 
                       'TasksToExecute',inf,           ... 
                       'ExecutionMode','fixedSpacing', ...
                       'TimerFcn',{@timerCallback,handles}); 
                  
global tm Tmem cnt_plot vplot vmem cvmem tmb tmbm vtmb vtmbm
global step Ts lenExp;
cvmem = ones(Pmax,1);
tmb = 1;
tmbm = 1;
lenExp = 20;
step = 0.01;
tm = 0:step:lenExp;
cnt_plot = 1;
vplot = zeros(length(tm),Pmax);
vmem = zeros(100000,Pmax);
Tmem = 0:step:step*length(vmem(:,1))-step;
Ts = 0.0001;

vtmb = ones(Pmax,1);
vtmbm = ones(Pmax,1);

global vscope scopetop receive_stat receive_Ptr iterator
scopetop = zeros(Pmax+1,1);
vscope = zeros(20000,Pmax+1);
receive_stat = 0;
receive_Ptr = 0;
iterator = 0;

% Update handles structure
guidata(hObject, handles);
start(handles.timer);
% UIWAIT makes MAS_Prog wait for user response (see UIRESUME)
% uiwait(handles.figure1);

function KeyPress(Source, EventData)
global ser conn
if(conn==1)

end


% UIWAIT makes INIT_Gui wait for user response (see UIRESUME)
% uiwait(handles.figure1);


% --- Outputs from this function are returned to the command line.
function varargout = INIT_Gui_OutputFcn(hObject, eventdata, handles) 
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;


% --- Executes on selection change in listbox1.
function listbox1_Callback(hObject, eventdata, handles)
% hObject    handle to listbox1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: contents = cellstr(get(hObject,'String')) returns listbox1 contents as cell array
%        contents{get(hObject,'Value')} returns selected item from listbox1


% --- Executes during object creation, after setting all properties.
function listbox1_CreateFcn(hObject, eventdata, handles)
% hObject    handle to listbox1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: listbox controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes on button press in pushbutton1.
function pushbutton1_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
instrreset
global conn nbdata ser
index_selected = get(handles.listbox1,'Value');
com = get(handles.listbox1,'String');
ser = serial(com(index_selected,:),'BaudRate',115200);
%ser = serial(com(index_selected,:),'BaudRate',230400);%115200);
%ser = serial(com(index_selected,:),'BaudRate',115200);
ser.InputBufferSize =nbdata;
ser.BytesAvailableFcnCount = 1500;
ser.BytesAvailableFcnMode = 'byte';
ser.BytesAvailableFcn = {@Serial_Receive, handles};
fopen(ser);
conn = 1;
TxRxUartCom(0,0,0,'D');
pause(0.5);
TxRxUartCom(0,0,0,'D');


% --- Executes on button press in pushbutton2.
function pushbutton2_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
set(handles.listbox1,'String',seriallist);

% --- Executes on button press in pushbutton3.
function pushbutton3_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton3 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
global exit
exit = 1;
close all;
closereq();

% --- Executes on button press in pushbutton4.
function pushbutton4_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton4 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
 TxUartCom(1,2,0);

% --- Executes on button press in pushbutton5.
function pushbutton5_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton5 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
 TxUartCom(1,2,1);

% --- Executes on button press in pushbutton6.
function pushbutton6_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton6 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
 TxUartCom(1,2,2);

% --- Executes on button press in pushbutton7.
function pushbutton7_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton7 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
TxUartCom(0,2,0);
TxUartCom(0,2,1);
TxUartCom(0,2,2);

% --- Executes on button press in pushbutton8.
function pushbutton8_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton8 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Par_Generic

% --- Executes on button press in pushbutton9.
function pushbutton9_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton9 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Plot_Generic

% --- Executes on button press in pushbutton10.
function pushbutton10_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton10 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Var_Generic

% --- Executes on button press in pushbutton11.
function pushbutton11_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton11 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
OBS_Generic

% --- Executes on button press in pushbutton12.
function pushbutton12_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton12 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Ident_Generic

% --- Executes on button press in pushbutton13.
function pushbutton13_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton13 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Others_Generic

% --- Executes on button press in pushbutton14.
function pushbutton14_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton14 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
global tm vplot step lenExp cvmem vmem Pmax
cvmem = ones(Pmax,1);
vmem = zeros(100000,Pmax);
tm = 0:step:lenExp;
vplot = zeros(length(tm),Pmax);

% --- Executes on button press in pushbutton15.
function pushbutton15_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton15 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
 global tm Tmem vplot vmem   
save('Vecfile.mat','tm','vplot');
save('VecfileMEM.mat','Tmem','vmem');

% --- Executes on button press in pushbutton17.
function pushbutton17_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton17 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
global vscope 
save('scopefile.mat','vscope');


% --- Executes on button press in pushbutton16.
function pushbutton16_Callback(hObject, eventdata, handles)
% hObject    handle to pushbutton16 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
TxRxUartCom(0,0,0,'D');
pause(0.5);
TxRxUartCom(0,0,0,'D');


function [] = timerCallback(hObject, eventdata, handles)
global ser exit
global nbdata conn
global var Dvar
global Plot_Mask Plot_i Plot_j Pmax
global tm cnt_plot vplot Ts step count_plot
global tmb 

%dVec = ( datevec(datetime('now' )));
 if ~isempty(handles)
   if (conn == 1)
   
     if(Ts ~= var(1,3))
         Ts = var(1,3);
         count_plot = floor(step/Ts);
         TxUartCom(count_plot,13,20);     %% to be changed accordingly
     end
      %Dvar 
     string1 = sprintf('%d', var(1,2));
     handles.text2.String = string1;

     %Plot in Axes 1  
   %   plot(handles.axes1,tm,vplot(:,1));
   %  hold( handles.axes1, 'on' )
   %   plot(handles.axes1,tm,vplot(:,2));
   %   plot(handles.axes1,tm,vplot(:,3));
   %   plot(handles.axes1,tm,vplot(:,4));
  %  plot(handles.axes1,tm,vplot(:,1:4));
    plot(handles.axes1,tm,vplot);
    hold( handles.axes1, 'off' )
    grid( handles.axes1, 'on' )
     
   end
 end

function Serial_Receive(hObject, eventdata, handles)
Serial_receive_fcn();

