function varargout = Plot_Generic(varargin)
% PLOT_GENERIC MATLAB code for Plot_Generic.fig
%      PLOT_GENERIC, by itself, creates a new PLOT_GENERIC or raises the existing
%      singleton*.
%
%      H = PLOT_GENERIC returns the handle to a new PLOT_GENERIC or the handle to
%      the existing singleton*.
%
%      PLOT_GENERIC('CALLBACK',hObject,eventData,handles,...) calls the local
%      function named CALLBACK in PLOT_GENERIC.M with the given input arguments.
%
%      PLOT_GENERIC('Property','Value',...) creates a new PLOT_GENERIC or raises the
%      existing singleton*.  Starting from the left, property value pairs are
%      applied to the GUI before Plot_Generic_OpeningFcn gets called.  An
%      unrecognized property name or invalid value makes property application
%      stop.  All inputs are passed to Plot_Generic_OpeningFcn via varargin.
%
%      *See GUI Options on GUIDE's Tools menu.  Choose "GUI allows only one
%      instance to run (singleton)".
%
% See also: GUIDE, GUIDATA, GUIHANDLES

% Edit the above text to modify the response to help Plot_Generic

% Last Modified by GUIDE v2.5 19-Mar-2022 13:25:16

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @Plot_Generic_OpeningFcn, ...
                   'gui_OutputFcn',  @Plot_Generic_OutputFcn, ...
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


% --- Executes just before Plot_Generic is made visible.
function Plot_Generic_OpeningFcn(hObject, eventdata, handles, varargin)
% This function has no output args, see OutputFcn.
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% varargin   command line arguments to Plot_Generic (see VARARGIN)

% Choose default command line output for Plot_Generic
handles.output = hObject;

handles.output = hObject;
 handles.timer = timer('Name','MyTimer',               ...
                       'Period',0.2,                    ... 
                       'StartDelay',1,                 ... 
                       'TasksToExecute',inf,           ... 
                       'ExecutionMode','fixedSpacing', ...
                       'TimerFcn',{@timerCallback_Var_Plot,handles}); 
% Update handles structure
guidata(hObject, handles);
start(handles.timer);

% UIWAIT makes Plot_Generic wait for user response (see UIRESUME)
% uiwait(handles.figure1);


% --- Outputs from this function are returned to the command line.
function varargout = Plot_Generic_OutputFcn(hObject, eventdata, handles) 
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;


% --- Executes on button press in radiobutton1.
function radiobutton1_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Plot_Fill_UART(handles.radiobutton1.Value,1,1);
% Hint: get(hObject,'Value') returns toggle state of radiobutton1


% --- Executes on button press in radiobutton2.
function radiobutton2_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
Plot_Fill_UART(handles.radiobutton2.Value,1,2);
% Hint: get(hObject,'Value') returns toggle state of radiobutton2


% --- Executes on button press in radiobutton3.
function radiobutton3_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton3 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton3.Value,1,3);
% Hint: get(hObject,'Value') returns toggle state of radiobutton3


% --- Executes on button press in radiobutton4.
function radiobutton4_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton4 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton4.Value,1,4);
% Hint: get(hObject,'Value') returns toggle state of radiobutton4


% --- Executes on button press in radiobutton5.
function radiobutton5_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton5 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton5.Value,1,5);
% Hint: get(hObject,'Value') returns toggle state of radiobutton5


% --- Executes on button press in radiobutton6.
function radiobutton6_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton6 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton6.Value,1,6);
% Hint: get(hObject,'Value') returns toggle state of radiobutton6


% --- Executes on button press in radiobutton7.
function radiobutton7_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton7 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton7.Value,1,7);
% Hint: get(hObject,'Value') returns toggle state of radiobutton7


% --- Executes on button press in radiobutton8.
function radiobutton8_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton8 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton8.Value,1,8);
% Hint: get(hObject,'Value') returns toggle state of radiobutton8


% --- Executes on button press in radiobutton9.
function radiobutton9_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton9 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton9.Value,1,9);
% Hint: get(hObject,'Value') returns toggle state of radiobutton9


% --- Executes on button press in radiobutton10.
function radiobutton10_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton10 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton10.Value,1,10);
% Hint: get(hObject,'Value') returns toggle state of radiobutton10


% --- Executes on button press in radiobutton11.
function radiobutton11_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton11 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton11.Value,1,11);
% Hint: get(hObject,'Value') returns toggle state of radiobutton11


% --- Executes on button press in radiobutton12.
function radiobutton12_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton12 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton12.Value,1,12);
% Hint: get(hObject,'Value') returns toggle state of radiobutton12


% --- Executes on button press in radiobutton13.
function radiobutton13_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton13 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton13.Value,1,13);
% Hint: get(hObject,'Value') returns toggle state of radiobutton13


% --- Executes on button press in radiobutton14.
function radiobutton14_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton14 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton14.Value,1,14);
% Hint: get(hObject,'Value') returns toggle state of radiobutton14


% --- Executes on button press in radiobutton15.
function radiobutton15_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton15 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton15.Value,1,15);
% Hint: get(hObject,'Value') returns toggle state of radiobutton15


% --- Executes on button press in radiobutton16.
function radiobutton16_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton16 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton16.Value,1,16);
% Hint: get(hObject,'Value') returns toggle state of radiobutton16


% --- Executes on button press in radiobutton17.
function radiobutton17_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton17 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton17.Value,1,17);
% Hint: get(hObject,'Value') returns toggle state of radiobutton17


% --- Executes on button press in radiobutton18.
function radiobutton18_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton18 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton18.Value,1,18);
% Hint: get(hObject,'Value') returns toggle state of radiobutton18


% --- Executes on button press in radiobutton19.
function radiobutton19_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton19 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton19.Value,1,19);
% Hint: get(hObject,'Value') returns toggle state of radiobutton19


% --- Executes on button press in radiobutton20.
function radiobutton20_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton20 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton20.Value,1,20);
% Hint: get(hObject,'Value') returns toggle state of radiobutton20


% --- Executes on button press in radiobutton21.
function radiobutton21_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton21 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton21.Value,1,21);
% Hint: get(hObject,'Value') returns toggle state of radiobutton21


% --- Executes on button press in radiobutton22.
function radiobutton22_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton22 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton22.Value,1,22);
% Hint: get(hObject,'Value') returns toggle state of radiobutton22


% --- Executes on button press in radiobutton23.
function radiobutton23_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton23 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton23.Value,1,23);
% Hint: get(hObject,'Value') returns toggle state of radiobutton23


% --- Executes on button press in radiobutton24.
function radiobutton24_Callback(hObject, eventdata, handles)
% hObject    handle to radiobutton24 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

Plot_Fill_UART(handles.radiobutton24.Value,1,24);
% Hint: get(hObject,'Value') returns toggle state of radiobutton24



 function [] = timerCallback_Var_Plot(hObject, eventdata, handles)
global ser exit
global nbdata conn
global var Dvar
global Plot_Mask Plot_i Plot_j Pmax
global tm cnt_plot vplot tmb

 if ~isempty(handles)     
   if (conn == 1)
    format shortg
    string1 = strcat(Dvar(1,1), sprintf(': %f', var(1,1)));
    handles.text2.String = string1;
   
    string1 = strcat(Dvar(1,2), sprintf(': %f', var(1,2)));
    handles.text3.String = string1;
    
    string1 = strcat(Dvar(1,3), sprintf(': %f', var(1,3)));
    handles.text4.String = string1;
    
    string1 = strcat(Dvar(1,4), sprintf(': %f', var(1,4)));
    handles.text5.String = string1;
    
    string1 = strcat(Dvar(1,5), sprintf(': %f', var(1,5)));
    handles.text6.String = string1;
    
    string1 = strcat(Dvar(1,6), sprintf(': %f', var(1,6)));
    handles.text7.String = string1;
    
    string1 = strcat(Dvar(1,7), sprintf(': %f', var(1,7)));
    handles.text8.String = string1;
    
    string1 = strcat(Dvar(1,8), sprintf(': %f', var(1,8)));
    handles.text9.String = string1;
    
    string1 = strcat(Dvar(1,9), sprintf(': %f', var(1,9)));
    handles.text10.String = string1;
    
    string1 = strcat(Dvar(1,10), sprintf(': %f', var(1,10)));
    handles.text11.String = string1;
    
    string1 = strcat(Dvar(1,11), sprintf(': %f', var(1,11)));
    handles.text12.String = string1;
    
    string1 = strcat(Dvar(1,12), sprintf(': %f', var(1,12)));
    handles.text13.String = string1;
    
    string1 = strcat(Dvar(1,13), sprintf(': %f', var(1,13)));
    handles.text14.String = string1;
    
    string1 = strcat(Dvar(1,14), sprintf(': %f', var(1,14)));
    handles.text15.String = string1;
    
    string1 = strcat(Dvar(1,15), sprintf(': %f', var(1,15)));
    handles.text16.String = string1;
    
    string1 = strcat(Dvar(1,16), sprintf(': %f', var(1,16)));
    handles.text17.String = string1;
    
    string1 = strcat(Dvar(1,17), sprintf(': %f', var(1,17)));
    handles.text18.String = string1;
    
    string1 = strcat(Dvar(1,18), sprintf(': %f', var(1,18)));
    handles.text19.String = string1;
    
    string1 = strcat(Dvar(1,19), sprintf(': %f', var(1,19)));
    handles.text20.String = string1;
    
    string1 = strcat(Dvar(1,20), sprintf(': %f', var(1,20)));
    handles.text21.String = string1;
    
    string1 = strcat(Dvar(1,21), sprintf(': %f', var(1,21)));
    handles.text22.String = string1;
    
    string1 = strcat(Dvar(1,22), sprintf(': %f', var(1,22)));
    handles.text23.String = string1;
    
    string1 = strcat(Dvar(1,23), sprintf(': %f', var(1,23)));
    handles.text24.String = string1;
    
    string1 = strcat(Dvar(1,24), sprintf(': %f', var(1,24)));
    handles.text25.String = string1;
    
    
   end
 end

