function y_out = Plot_Fill_UART(val,x,y)

global Plot_Mask Plot_i Plot_j Pmax
if(val == 1)
    i=1;
    while(Plot_Mask(i)== 1 && i<=Pmax)
        i=i+1;
    end 
    if(i<=Pmax)
        Plot_Mask(i) = 1;
        Plot_i(i) = x;
        Plot_j(i) = y;
    end
else   
    for i=1:Pmax
        if(Plot_i(i)==x && Plot_j(i)==y)
            Plot_Mask(i) = 0;
            Plot_i(i) = 0;
            Plot_j(i) = 0;
        end
    end
    
end

if Pmax<=10
 for k=1:Pmax
    if(Plot_Mask(k)== 1)
        TxUartCom(Plot_i(k)-1,13,2*(k-1));
        TxUartCom(Plot_j(k)-1,13,2*(k-1)+1);
        
        %% optional
        TxUartCom(Plot_i(k)-1,3,9+k);
        TxUartCom(Plot_j(k)-1,3,14+k);
    else
        TxUartCom(255,13,2*(k-1));
        TxUartCom(255,13,2*(k-1)+1);
        
        %% optional
        TxUartCom(255,3,9+k);
        TxUartCom(255,3,14+k);          
    end
 end
else
   for k=1:10
    if(Plot_Mask(k)== 1)
        TxUartCom(Plot_i(k)-1,13,2*(k-1));
        TxUartCom(Plot_j(k)-1,13,2*(k-1)+1);
        
        %% optional
        TxUartCom(Plot_i(k)-1,3,9+k);
        TxUartCom(Plot_j(k)-1,3,14+k);
    else
        TxUartCom(255,13,2*(k-1));
        TxUartCom(255,13,2*(k-1)+1);
        
        %% optional
        TxUartCom(255,3,9+k);
        TxUartCom(255,3,14+k);          
    end
   end
   for k=11:Pmax
      if(Plot_Mask(k)== 1)
        TxUartCom(Plot_i(k)-1,14,2*(k-11));
        TxUartCom(Plot_j(k)-1,14,2*(k-11)+1);
        
        %% optional
       %% TxUartCom(Plot_i(k)-1,3,9+k);
       %% TxUartCom(Plot_j(k)-1,3,14+k);
    else
        TxUartCom(255,14,2*(k-11));
        TxUartCom(255,14,2*(k-11)+1);
        
        %% optional
     %%   TxUartCom(255,3,9+k);
     %%   TxUartCom(255,3,14+k);          
    end 
   end
end

y_out = 1;