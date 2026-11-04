-- Northwind SQLite Schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS `categories` (
    `categoryID` INTEGER PRIMARY KEY,
    `categoryName` TEXT NOT NULL,
    `description` TEXT,
    `picture` TEXT
);

CREATE TABLE IF NOT EXISTS `suppliers` (
    `supplierID` INTEGER PRIMARY KEY,
    `companyName` TEXT NOT NULL,
    `contactName` TEXT,
    `contactTitle` TEXT,
    `address` TEXT,
    `city` TEXT,
    `region` TEXT,
    `postalCode` TEXT,
    `country` TEXT,
    `phone` TEXT,
    `fax` TEXT,
    `homePage` TEXT
);

CREATE TABLE IF NOT EXISTS `customers` (
    `customerID` TEXT PRIMARY KEY,
    `companyName` TEXT NOT NULL,
    `contactName` TEXT,
    `contactTitle` TEXT,
    `address` TEXT,
    `city` TEXT,
    `region` TEXT,
    `postalCode` TEXT,
    `country` TEXT,
    `phone` TEXT,
    `fax` TEXT
);

CREATE TABLE IF NOT EXISTS `shippers` (
    `shipperID` INTEGER PRIMARY KEY,
    `companyName` TEXT NOT NULL,
    `phone` TEXT
);

CREATE TABLE IF NOT EXISTS `regions` (
    `regionID` INTEGER PRIMARY KEY,
    `regionDescription` TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS `territories` (
    `territoryID` TEXT PRIMARY KEY,
    `territoryDescription` TEXT NOT NULL,
    `regionID` INTEGER NOT NULL,
    FOREIGN KEY (`regionID`) REFERENCES `regions`(`regionID`)
);

CREATE TABLE IF NOT EXISTS `employees` (
    `employeeID` INTEGER PRIMARY KEY,
    `lastName` TEXT NOT NULL,
    `firstName` TEXT NOT NULL,
    `title` TEXT,
    `titleOfCourtesy` TEXT,
    `birthDate` TEXT,
    `hireDate` TEXT,
    `address` TEXT,
    `city` TEXT,
    `region` TEXT,
    `postalCode` TEXT,
    `country` TEXT,
    `homePhone` TEXT,
    `extension` TEXT,
    `photo` TEXT,
    `notes` TEXT,
    `reportsTo` INTEGER,
    `photoPath` TEXT,
    FOREIGN KEY (`reportsTo`) REFERENCES `employees`(`employeeID`)
);

CREATE TABLE IF NOT EXISTS `employee_territories` (
    `employeeID` INTEGER,
    `territoryID` TEXT,
    PRIMARY KEY (`employeeID`, `territoryID`),
    FOREIGN KEY (`employeeID`) REFERENCES `employees`(`employeeID`),
    FOREIGN KEY (`territoryID`) REFERENCES `territories`(`territoryID`)
);

CREATE TABLE IF NOT EXISTS `products` (
    `productID` INTEGER PRIMARY KEY,
    `productName` TEXT NOT NULL,
    `supplierID` INTEGER,
    `categoryID` INTEGER,
    `quantityPerUnit` TEXT,
    `unitPrice` REAL,
    `unitsInStock` INTEGER,
    `unitsOnOrder` INTEGER,
    `reorderLevel` INTEGER,
    `discontinued` INTEGER,
    FOREIGN KEY (`supplierID`) REFERENCES `suppliers`(`supplierID`),
    FOREIGN KEY (`categoryID`) REFERENCES `categories`(`categoryID`)
);

CREATE TABLE IF NOT EXISTS `orders` (
    `orderID` INTEGER PRIMARY KEY,
    `customerID` TEXT,
    `employeeID` INTEGER,
    `orderDate` TEXT,
    `requiredDate` TEXT,
    `shippedDate` TEXT,
    `shipVia` INTEGER,
    `freight` REAL,
    `shipName` TEXT,
    `shipAddress` TEXT,
    `shipCity` TEXT,
    `shipRegion` TEXT,
    `shipPostalCode` TEXT,
    `shipCountry` TEXT,
    FOREIGN KEY (`customerID`) REFERENCES `customers`(`customerID`),
    FOREIGN KEY (`employeeID`) REFERENCES `employees`(`employeeID`),
    FOREIGN KEY (`shipVia`) REFERENCES `shippers`(`shipperID`)
);

CREATE TABLE IF NOT EXISTS `order_details` (
    `orderID` INTEGER,
    `productID` INTEGER,
    `unitPrice` REAL NOT NULL,
    `quantity` INTEGER NOT NULL,
    `discount` REAL NOT NULL,
    PRIMARY KEY (`orderID`, `productID`),
    FOREIGN KEY (`orderID`) REFERENCES `orders`(`orderID`),
    FOREIGN KEY (`productID`) REFERENCES `products`(`productID`)
);
