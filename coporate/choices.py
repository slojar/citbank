MANDATE_TYPE_CHOICES = (
    ("uploader", "Uploader"), ("verifier", "Verifier"), ("authorizer", "Authorizer")
)

TRANSFER_REQUEST_STATUS = (
    ("pending", "Pending"), ("approved", "Approved"), ("declined", "Declined")
)

TRANSFER_REQUEST_OPTION = (
    ("single", "Single"), ("bulk", "Bulk")
)

SCHEDULE_TYPE = (
    ("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly"),
    ("bi-annually", "Bi-annually"), ("yearly", "Yearly"), ("once", "One Time")
)

DAYS_OF_THE_MONTH_CHOICES = (
    ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'), ('7', '7'), ('8', '8'),
    ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12'), ('13', '13'), ('14', '14'), ('15', '15'), ('16', '16'),
    ('17', '17'), ('18', '18'), ('19', '19'), ('20', '20'), ('21', '21'), ('22', '22'), ('23', '23'), ('24', '24'),
    ('25', '25'), ('26', '26'), ('27', '27'), ('28', '28'), ('29', '29'), ('30', '30'), ('31', '31')
)

DAY_OF_THE_WEEK_CHOICES = (
    ('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', 'Thursday'), ('5', 'Friday'), ('6', 'Saturday'),
    ('7', 'Sunday')
)

TRANSFER_SCHEDULE_STATUS = (
    ("active", "Active"), ("inactive", "Inactive")
)


