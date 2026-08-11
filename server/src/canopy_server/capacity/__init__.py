"""The capacity layer (design/organizations/02–03, milestone C2): provider quota as a
first-class, provider-truthful resource.

Capacity is not budget: the BudgetLedger states *demand* (allowances the operator set);
this layer states *supply* (windows the provider defines, moved by everything the operator
runs — including their own interactive usage outside Canopy). Levels come from the
provider wherever a surface exists; every number carries its source tier and age.
"""

from .accounts import ProviderAccount, ProviderAccountStore
from .ledger import CapacityLedger
from .service import CapacityService

__all__ = ["ProviderAccount", "ProviderAccountStore", "CapacityLedger", "CapacityService"]
