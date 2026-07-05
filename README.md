graph BT
  %% Define the sage green styling
  classDef root fill:#4B6B49,stroke:#E1EFE0,stroke-width:2px,color:#FFF,rx:8px,ry:8px;
  classDef branch fill:#6A8D67,stroke:#E1EFE0,stroke-width:2px,color:#FFF,rx:8px,ry:8px;
  classDef leaf fill:#9DC183,stroke:#E1EFE0,stroke-width:2px,color:#1A2F18,rx:8px,ry:8px;

  %% Nodes
  Root[Root Intent]:::root
  
  M1[Manager]:::branch
  M2[Manager]:::branch
  M3[Manager]:::branch

  IC1[Agent]:::leaf
  IC2[Agent]:::leaf
  IC3[Agent]:::leaf
  IC4[Agent]:::leaf
  IC5[Agent]:::leaf
  IC6[Agent]:::leaf
  IC7[Agent]:::leaf

  %% Connections branching UP
  M1 --- Root
  M2 --- Root
  M3 --- Root

  IC1 --- M1
  IC2 --- M1

  IC3 --- M2
  IC4 --- M2
  IC5 --- M2
  
  IC6 --- M3
  IC7 --- M3
  
  linkStyle default stroke:#A3C1AD,stroke-width:2px;