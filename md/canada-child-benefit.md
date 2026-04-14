# Canada Child Benefit

A tax-free monthly payment to eligible families to help with the cost of raising children under 18 years of age.

- **Administered by:** Canada Revenue Agency
- **Effective date:** 2025-07-01
- **Status:** active

## Eligibility

You must live with a child under 18, be primarily responsible for their care, and be a Canadian resident for tax purposes.

- You live with a child who is under 18 years of age
- You are primarily responsible for the care and upbringing of the child
- You are a resident of Canada for tax purposes
- You or your spouse/common-law partner must have qualifying immigration status

## Amounts

The amount depends on your adjusted family net income (AFNI), the number of children, and their ages.

### Key values

| Parameter | Value |
|---|---|
| Maximum eligible age | 18 years |
| Age cutoff for higher benefit rate | 6 years |
| Maximum annual benefit per child under 6 | $7,997 |
| Maximum annual benefit per child aged 6 to 17 | $6,748 |
| First income threshold (no reduction below this) | $37,487 |
| Second income threshold (higher reduction rate above this) | $81,222 |

### Calculation rules

1. Sum the maximum annual benefit for each child based on age. 2. If family income exceeds the first threshold, reduce the total using the applicable rate from the reduction table.

**Maximum benefit per child:**

- If child_age < 6: $7,997/year
- If child_age >= 6: $6,748/year

**Income reduction brackets:**

- income <= 37,487: none
- 37,487 < income <= 81,222: total_max - rate_mid * (income - 37,487)
- income > 81,222: total_max - base_reduction - rate_high * (income - 81,222)

**Reduction table:**

| Children | Mid-bracket rate | High-bracket rate | Base reduction |
|---|---|---|---|
| 1 | 7% | 3.2% | $3,061 |
| 2 | 13.5% | 5.7% | $5,904 |
| 3 | 19% | 8% | $8,310 |
| 4+ | 23% | 9.5% | $10,059 |

### Examples

- **Martha: 1 child under 6, AFNI $45,000 (mid bracket)** → $7,471.09/year, $622.59/month
- **Martha: 1 child under 6, AFNI $100,000 (high bracket)** → $4,335.11/year, $361.25/month
- **Fatima: 2 children under 6, AFNI $60,000 (mid bracket)** → $12,954.75/year, $1,079.56/month
- **Fatima: 2 children under 6, AFNI $125,000 (high bracket)** → $7,594.66/year, $632.88/month
- **Julie: 3 children over 6, AFNI $50,000 (mid bracket)** → $17,866.53/year, $1,488.87/month
- **Julie: 3 children over 6, AFNI $150,000 (high bracket)** → $6,431.76/year, $535.98/month
- **Kira: 4 children over 6, AFNI $45,000 (mid bracket)** → $25,264.01/year, $2,105.33/month
- **Kira: 4 children over 6, AFNI $200,000 (high bracket)** → $5,649.09/year, $470.75/month

## How to apply

- **Birth-Registration:** Apply when you register the birth of your newborn with your province or territory.
- **Online:** Apply through CRA My Account
- **Mail:** Fill out Form RC66, Canada Child Benefits Application, and mail it to your tax centre.

## Processing time

Online applications: about 8 weeks. Mail applications: about 11 weeks.

## Fees

There is no fee to apply for or receive the Canada Child Benefit.
