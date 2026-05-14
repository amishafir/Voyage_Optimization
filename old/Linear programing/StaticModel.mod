/*********************************************
 * OPL 22.1.1.0 Model
 * Author: talraviv
 * Creation Date: Mar 17, 2025 at 5:17:45 PM
 *********************************************/

float ETA = ...;

int num_segments = ...;
int num_speeds = ...;

range segments = 1..num_segments;
range speeds = 1..num_speeds;
 
 
float l[segments] = ...;  // length of segments in miles
float L[segments] = ...;
float U[segments] = ...;
float s[speeds] = ...;
float FCR[speeds] = ...; 
 
float f[segments, speeds]  =  ...;


dvar boolean x[segments, speeds];

dexpr float sws[i in segments] = sum( k in speeds)  s[k]* x[i,k];
dexpr float sog[i in segments] = sum( k in speeds)  f[i,k]* x[i,k];

dexpr float T = sum(i in segments) l[i]/ sog[i];

minimize sum(i in segments) l[i] * sum(k in speeds) x[i,k]* FCR[k] / f[i,k];
subject to {
  sum(i in segments, k in speeds) (l[i]/ f[i,k]) * x[i,k]  <= ETA;
  forall(i in segments)  sum(k in speeds) x[i,k] == 1; 
  forall (i in segments)  L[i] <= sum(k in speeds) f[i,k] * x[i,k] <= U[i];
  
}

execute {
  writeln(sog);
  writeln(sws);
  writeln(T);
}
 
 
 
 
 
 