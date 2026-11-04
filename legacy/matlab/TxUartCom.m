function y_out = TxUartCom(fl,pos1,pos2)

global ser
%% start sequence
fwrite(ser,"s");
fwrite(ser,"t");
fwrite(ser,"x");

%% info
fwrite(ser,uint8(pos1));
fwrite(ser,uint8(pos2));
fwrite(ser,uint8(0));
%fwrite(ser,uint8('S'));
fwrite(ser,uint8(0));

%% Data
p = typecast(single(fl), 'uint8');
fwrite(ser,uint8(p(1)));
fwrite(ser,uint8(p(2)));
fwrite(ser,uint8(p(3)));
fwrite(ser,uint8(p(4)));

y_out=1;