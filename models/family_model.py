# coding=utf-8
"""
Contains all the models related to families in the system
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import BigInteger, Boolean, Column, DateTime, FetchedValue, ForeignKey, Integer, String, VARCHAR
from sqlalchemy.orm import backref, relationship

from main import db


class Group(db.Model):
    """
    Specifies how groups are modeled in the database

    @param group_id: group's ID
    @param group_name: 255 letter name of the group
    """
    __tablename__ = "groups"

    id: int = Column(BigInteger, server_default=FetchedValue(), primary_key=True, unique=True, nullable=False)
    name: str = Column(VARCHAR(255), nullable=True)
    description: str = Column(VARCHAR(255), nullable=True)

    families: List[Family] = relationship(
        "Family",
        secondary="families_groups",
        backref=backref("Group", lazy="dynamic")
    )

    def __init__(self, group_id: int, group_name: str):
        self.id = group_id
        self.name = group_name

    def __repr__(self):
        return "<id {}>".format(self.id)


class Family(db.Model):
    """
    Specifies how families are modeled in the database

    @param family_id: family's ID
    @param family_group: group where the family belongs ID
    @param family_name: 255 letter name of the group
    """

    __tablename__ = "families"
    id: int = Column(BigInteger, server_default=FetchedValue(), primary_key=True, unique=True, nullable=False)
    name: str = Column(String(255), nullable=False)
    creation: datetime = Column(DateTime, nullable=False, default=datetime.now())

    groups: List[Group] = relationship(
        Group,
        secondary="families_groups",
        backref=backref("Family", lazy="dynamic")
    )

    def __init__(self, family_id, family_group, family_name):
        self.id = family_id
        self.group = family_group
        self.name = family_name

    def __repr__(self):
        return "<id {}>".format(self.id)


class FamilyGroup(db.Model):
    """
    Specifies how family-group relationships are defined in the database

    @param family_id: family's ID
    @param group_id: ID of the group where the family belongs
    @param confirmed: if the family has been authorized to be in the group
    """

    __tablename__ = "families_groups"
    family_id: int = Column(Integer, ForeignKey(Family.id), primary_key=True, unique=False, nullable=False)
    group_id: int = Column(Integer, ForeignKey(Group.id), unique=False, nullable=False)
    confirmed: bool = Column(Boolean, default=False, unique=False, nullable=False)

    def __init__(self, family_id: int, group_id: int, confirmed: bool = False):
        self.family_id = family_id
        self.group_id = group_id
        self.confirmed = confirmed

    def __repr__(self):
        return "<id {}>".format(self.family_id)

