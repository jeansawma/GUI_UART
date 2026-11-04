function y_out = Serial_receive_fcn()

global ser exit
global nbdata conn
global Plot_Mask vplot vmem cvmem Plot_i Plot_j Pmax
global var Dvar tmb tmbm tm
global step Ts lenExp
global vec_old count_plot vtmbm vtmb
global vscope scopetop receive_stat receive_Ptr iterator


if(exit==0)
    x= fread(ser,1500);
    a = [vec_old ; x];  
	len = length(a);
    breakW = 0;
    
    for o = 1:Pmax
        if(cvmem(o)>97000)
            cvmem(o) = 1;
        end
    end

    cnt = 0;
    i = 1;
    if(receive_Ptr~=0)
        [iterator scopetop(receive_Ptr)]
        while(i<=len-3 && iterator<scopetop(receive_Ptr))
            i = i + 4;
            iterator = iterator+1;
            v1 = a(i-4);
            v2 = a(i-3);
            v3 = a(i-2);
            v4 = a(i-1);
            vscope(iterator,receive_Ptr) = typecast(uint8([v1 v2 v3 v4]), 'single');  
        end

        if(iterator>=scopetop(receive_Ptr))
            fprintf('sent')
            iterator=0;
            receive_Ptr = 0;
        end
    end
    
    while(i<len-500 && breakW==0) 
        while(i<len-500 && cnt < 3)
            if(a(i)=='s')
                cnt = 1;
            elseif(a(i)=='t' && cnt == 1)
                cnt = 2;
            elseif(a(i)=='x' && cnt == 2)
                cnt = 3;
            elseif(a(i)=='d' && cnt == 2)
                cnt = 4;
            elseif(a(i)=='v' && cnt == 2)
                cnt = 5;
            else
                 cnt = 0;
            end
            i = i+1;
        end
        if(cnt == 5) 
            receive_Ptr=a(i+1);
            scopetop(receive_Ptr)=a(i+2)+a(i+3)*100+a(i+4)*10000;
            [receive_Ptr a(i+2)+a(i+3)*100+a(i+4)*10000 123456]
            breakW = 1;
            i = i+7;
        elseif(cnt==4)     
            x=a(i+1);
            y=a(i+2);
            z=a(i+3); 
            %[x y a(i+7:i+7+z-1)']
            Dvar(x+1,y+1)=char(a(i+7:i+7+z-1)');
            
        elseif(cnt==3)
            x=a(i+1);
            y=a(i+2);
            if(a(i+3)~=0 && y<=100 && x>=0 && x<200)
                for j = 0: y-1
                    v1 = a(i+7+j*4);
                    v2 = a(i+8+j*4);
                    v3 = a(i+9+j*4);
                    v4 = a(i+10+j*4);
                    var(x+1,j+1)= typecast(uint8([v1 v2 v3 v4]), 'single'); 
                end 
            elseif(y>=0 && y<=100 && x>=200 && x<=255)
                %[x y count_plot var(14,1) var(14,2) var(14,3) var(14,4)]
                
                v1 = a(i+7+y*4);
                v2 = a(i+8+y*4);
                v3 = a(i+9+y*4);
                v4 = a(i+10+y*4);
                tmb = typecast(uint8([v1 v2 v3 v4]), 'int32');
                tmb = mod(single(single(tmb)*Ts),lenExp);                        
                tmb = floor(tmb/step) + 1;
         
                if(Plot_Mask(x-199)==1) 
                    
                    for j = 0: y-1
                        v1 = a(i+7+j*4);
                        v2 = a(i+8+j*4);
                        v3 = a(i+9+j*4);
                        v4 = a(i+10+j*4);
                        if(tmb+j<length(tm))
                            if(j==0)
                                if(tmb>=vtmbm(x-199))
                                    vplot(vtmbm(x-199)+1:tmb,x-199)=  typecast(uint8([v1 v2 v3 v4]), 'single');
                                    vmem(cvmem(x-199):cvmem(x-199) + (tmb-vtmbm(x-199)-1),x-199) = typecast(uint8([v1 v2 v3 v4]), 'single');
                                    cvmem(x-199) = cvmem(x-199) + (tmb-vtmbm(x-199));
                                elseif(vtmbm(x-199)-tmb>length(tm)/2)
                                    vplot(vtmbm(x-199)+1:length(tm),x-199)= typecast(uint8([v1 v2 v3 v4]), 'single');
                                    vplot(1:tmb,x-199)= typecast(uint8([v1 v2 v3 v4]), 'single');
                                    
                                 %   vmem(cvmem(x-199):cvmem(x-199) + (tmb-vtmbm(x-199)),x-199) = typecast(uint8([v1 v2 v3 v4]), 'single');
                                 %   cvmem(x-199) = cvmem(x-199) + (tmb-vtmbm(x-199)+1);
                                end
                            else
                               vplot(tmb+j,x-199)= typecast(uint8([v1 v2 v3 v4]), 'single');
                               vmem(cvmem(x-199),x-199)= typecast(uint8([v1 v2 v3 v4]), 'single');
                               cvmem(x-199) = cvmem(x-199) + 1;
                            end
                        end
                    end
                 vtmbm(x-199) = tmb + y -1; 
                else
                    vplot(:,x-199)=0;
                end         
                            
                 i = i+10+(y-1)*4;                 
            else
                %% send a starting sequence
            end
        end
        cnt = 0;
    end
    vec_old = a(i:length(a));
else
    fclose(ser);
end

y_out = 1;